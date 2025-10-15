from flask import Flask, render_template, request, redirect, url_for, Response, jsonify, session
import pandas as pd
import io
import re
import threading
import time
import os
from helper import important_words_from_texts, generate_ngrams, generate_podcast_strings_for_keywordplanner
from queries_list import one_word_list, two_word_list, synonym_for_one_word, synonym_for_two_word
import uuid
try:
    from cachetools import TTLCache
    CACHETOOLS_AVAILABLE = True
except ImportError:
    # Fallback for environments without cachetools
    CACHETOOLS_AVAILABLE = False
    print("Warning: cachetools not available, using fallback cache")

app = Flask(__name__)
# Use environment variable for secret key in production, fallback for development
app.secret_key = os.environ.get('SECRET_KEY', 'super_secret_key_dev_only')

# Create a TTL cache: maxsize=100 means it can hold up to 100 users' data at once  - ttl=14400 means each user's data lives for 4 hours (14400 seconds)
if CACHETOOLS_AVAILABLE:
    user_data = TTLCache(maxsize=100, ttl=14400)
else:
    # Fallback: simple dict with manual cleanup
    user_data = {}

# Thread lock for thread-safe operations
data_lock = threading.Lock()


def get_user_id():
    """Assign or retrieve a unique session ID for each user."""
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
    return session['user_id']

def get_user_data(user_id: str | None = None):
    """Get the user's full data dict (or empty if not set).
    If user_id is provided, use it (for background threads). Otherwise, use the session-bound id.
    """
    with data_lock:
        uid = user_id or get_user_id()
        return user_data.get(uid, {})

def save_user_data(new_data: dict, user_id: str | None = None):
    """Update or overwrite per-user data and refresh TTL.
    If user_id is provided, use it (for background threads). Otherwise, use the session-bound id.
    """
    with data_lock:
        uid = user_id or get_user_id()
        data = user_data.get(uid, {})
        data.update(new_data)
        user_data[uid] = data  # refresh TTL








# HOME PAGE
@app.route("/", methods=["GET", "POST"])
def home():
    message = None
    table_html = None

    if request.method == "POST":
        try:
            file = request.files.get("file")
            if file and file.filename.endswith(".csv"):
                df = pd.read_csv(file)
                uploaded_filename = file.filename

                # Validate required columns
                if "Title" not in df.columns or "Description" not in df.columns:
                    message = "CSV must contain columns: Title, Description"
                    return render_template("home.html", rows=None, cols=None, filename=None, message=message, table=None)

                # Column handling rules:
                # - If CSV has only Title and Description, add 3 new columns with defaults
                # - If it has 3+ columns, preserve provided values; only add missing required columns with defaults
                existing_cols = set(df.columns)
                required_defaults = {
                    "Analyzed": False,
                    "No of Queries": 0,
                    "Added Queries": ""
                }
                # Only add the three tracking columns if missing; do not create important_words here
                for col, default_val in required_defaults.items():
                    if col not in existing_cols:
                        df[col] = default_val

                message = "CSV uploaded successfully. Click 'Generate Important Queries' to continue."

                # Save all user-specific data in cache
                save_user_data({
                    "df": df,
                    "uploaded_filename": uploaded_filename,
                    "current_csv_file": uploaded_filename,  # optional
                    "processing_state": {}  # Reset processing state
                })
            else:
                message = "Please upload a valid CSV file."
        except Exception as e:
            message = f"Error processing CSV file: {str(e)}"
            return render_template("home.html", rows=None, cols=None, filename=None, message=message, table=None)

            


    # Retrieve user's DataFrame if exists
    user = get_user_data()
    df = user.get("df")
    uploaded_filename = user.get("uploaded_filename")


    # If a CSV is already uploaded, render the table
    if df is not None:
        table_html = df.to_html(classes="table table-striped", index=False)

    rows = df.shape[0] if df is not None else None
    cols = df.shape[1] if df is not None else None

    return render_template("home.html",
                           rows=rows,
                           cols=cols,
                           filename=uploaded_filename,
                           message=message,
                           table=table_html)




# BACKGROUND PROCESSING
def process_important_words(uid: str):
    try:
        user = get_user_data(uid)
        df = user.get("df")
        processing_state = user.get("processing_state", {})
        
        if df is None:
            # Update processing state to error
            processing_state.update({
                "percent": 0,
                "eta": "00:00:00",
                "done": False,
                "in_progress": False,
                "error": "No data available"
            })
            save_user_data({"processing_state": processing_state}, user_id=uid)
            return
        
        total_rows = len(df)
        batch_size = 10
        important_words_list = []

        # Initialize processing state
        processing_state.update({
            "in_progress": True,
            "started_at": time.time(),
            "percent": 0,
            "eta": "00:00:00",
            "done": False,
            "error": None
        })
        save_user_data({"processing_state": processing_state}, user_id=uid)

        for start in range(0, total_rows, batch_size):
            end = min(start + batch_size, total_rows)
            batch_texts = df["Description"].iloc[start:end].tolist()
            
            try:
                batch_words = important_words_from_texts(batch_texts)
                important_words_list.extend(batch_words)
            except Exception as e:
                # Handle batch processing error
                processing_state.update({
                    "percent": 0,
                    "eta": "00:00:00",
                    "done": False,
                    "in_progress": False,
                    "error": f"Processing error: {str(e)}"
                })
                save_user_data({"processing_state": processing_state})
                return
            
            # Update progress & ETA
            processed = end
            progress_ratio = processed / max(total_rows, 1)
            processing_state["percent"] = int(progress_ratio * 100)
            elapsed = time.time() - (processing_state["started_at"] or time.time())
            # Avoid division by zero for very first batch
            if progress_ratio > 0:
                estimated_total = elapsed / progress_ratio
                remaining = max(0, estimated_total - elapsed)
            else:
                remaining = 0
            hrs = int(remaining // 3600)
            mins = int((remaining % 3600) // 60)
            secs = int(remaining % 60)
            processing_state["eta"] = f"{hrs:02d}:{mins:02d}:{secs:02d}"
            
            # Save updated state back to user cache
            save_user_data({"processing_state": processing_state}, user_id=uid)
            time.sleep(0.001)  # small delay

        # Save the results to the user's DataFrame
        df["Important Words"] = important_words_list

        # Update processing state to finished
        processing_state.update({
            "percent": 100,
            "eta": "00:00:00",
            "done": True,
            "in_progress": False,
            "error": None
        })

        # Save final state and updated DataFrame back to user cache
        save_user_data({
            "df": df,
            "processing_state": processing_state
        }, user_id=uid)
        
    except Exception as e:
        # Handle any unexpected errors
        processing_state = get_user_data(uid).get("processing_state", {})
        processing_state.update({
            "percent": 0,
            "eta": "00:00:00",
            "done": False,
            "in_progress": False,
            "error": f"Unexpected error: {str(e)}"
        })
        save_user_data({"processing_state": processing_state}, user_id=uid)





# START PROCESSING
@app.route("/process", methods=["POST"])
def process():
    try:
        user = get_user_data()
        df = user.get("df")
        processing_state = user.get("processing_state", {})

        if df is None:
            return jsonify({"status": "no_csv_uploaded", "error": "No CSV uploaded yet"}), 400
        
        # If already processed (has important_words with any non-null), just redirect to results
        if "Important Words" in df.columns and df["Important Words"].notna().any():
            return jsonify({"status": "already_processed", "redirect": url_for("results")})

        # If already running, just acknowledge
        if processing_state and processing_state.get("in_progress") and not processing_state.get("done"):
            return jsonify({"status": "already_running"})

        # If there was a previous error, reset the state
        if processing_state.get("error"):
            processing_state = {}

        # Initialize or reset processing_state
        processing_state = {
            "in_progress": True,
            "started_at": time.time(),
            "percent": 0,
            "eta": "00:00:00",
            "done": False,
            "error": None
        }

        # Save state tied to this user id
        uid = get_user_id()
        save_user_data({"processing_state": processing_state}, user_id=uid)

        # Start processing in a background thread
        thread = threading.Thread(target=process_important_words, args=(uid,), daemon=True)
        thread.start()
        return jsonify({"status": "started"})
        
    except Exception as e:
        return jsonify({"status": "error", "error": f"Failed to start processing: {str(e)}"}), 500





# PROGRESS POLLING
@app.route("/progress", methods=["GET"])
def progress():
    try:
        user = get_user_data()
        processing_state = user.get("processing_state", {})

        return jsonify({
            "in_progress": bool(processing_state.get("in_progress", False)),
            "percent": int(processing_state.get("percent", 0)),
            "eta": processing_state.get("eta", "00:00:00"),
            "done": bool(processing_state.get("done", False)),
            "error": processing_state.get("error")
        })
    except Exception as e:
        return jsonify({
            "in_progress": False,
            "percent": 0,
            "eta": "00:00:00",
            "done": False,
            "error": f"Failed to get progress: {str(e)}"
        })






# RESULTS PAGE - FULL PAGE
@app.route("/results", methods=["GET", "POST"])
def results():
    try:
        user = get_user_data()
        df = user.get("df")
        
        if df is None:
            return render_template(
                "results.html",
                message="Processing not done yet. Please upload a CSV first.",
                download_ready=False,
                analyzed_count=0,
                total_episodes=0
            )
    except Exception as e:
        return render_template(
            "results.html",
            message=f"Error loading results: {str(e)}",
            download_ready=False,
            analyzed_count=0,
            total_episodes=0
        )

    # Compute analyzed and total counts
    try:
        analyzed_count = int(df["Analyzed"].sum()) if "Analyzed" in df.columns else 0
    except Exception:
        analyzed_count = 0
    total_episodes = int(df.shape[0])

    # POST: when user clicks "Get Suggestions" button
    if request.method == "POST":
        title = request.form.get("title")
        if not title or title not in df["Title"].values:
            return render_template(
                "results.html",
                titles=df["Title"].tolist(),
                download_ready=("Important Words" in df.columns),
                analyzed_count=analyzed_count,
                total_episodes=total_episodes
            )

        row = df[df["Title"] == title].iloc[0]

        # Ensure important words exist for this episode
        iw_value = row.get("Important Words") if isinstance(row, dict) else row["Important Words"]
        if not iw_value or (isinstance(iw_value, float) and pd.isna(iw_value)) or (isinstance(iw_value, str) and not iw_value.strip()):
            desc_text = row["Description"]
            computed = important_words_from_texts([desc_text])
            iw_string = computed[0] if isinstance(computed, (list, tuple)) and computed else ""
            df.loc[df["Title"] == title, "Important Words"] = iw_string
            iw_value = iw_string

            # Save updated DataFrame back to cache
            save_user_data({"df": df})

        words = (iw_value or "").split()

        one_word = generate_ngrams(words, n=1)
        two_word = generate_ngrams(words, n=2)
        one_word_podcasts = generate_ngrams(words, n=1, append_label="podcasts")
        two_word_podcasts = generate_ngrams(words, n=2, append_label="podcasts")

        one_word_text, two_word_text = generate_podcast_strings_for_keywordplanner(
            one_word, two_word, red_one_word=one_word_list, red_two_word=two_word_list
        )

        titles_with_index = [(i + 1, t) for i, t in enumerate(df["Title"].tolist())]
        true_count = df['Analyzed'].sum()

        return render_template(
            "results.html",
            titles=titles_with_index,
            selected_title=title,
            no_of_episodes_analysed=true_count,
            one_word=one_word,
            two_word=two_word,
            one_word_podcasts=one_word_podcasts,
            two_word_podcasts=two_word_podcasts,
            red_one_word=one_word_list,
            red_two_word=two_word_list,
            yellow_one_word=synonym_for_one_word,
            yellow_two_word=synonym_for_two_word,
            one_word_podcast_text=one_word_text,
            two_word_podcast_text=two_word_text,
            download_ready=True,
            episode_analyzed=row.get("Analyzed", False),
            queries_count=row.get("No of Queries", 0),
            analyzed_count=analyzed_count,
            total_episodes=total_episodes
        )

    # GET: base page (initial load, no suggestions yet)
    return render_template(
        "results.html",
        titles=df["Title"].tolist(),
        download_ready=("Important Words" in df.columns),
        analyzed_count=analyzed_count,
        total_episodes=total_episodes
    )






@app.route("/get_suggestions", methods=["POST"])
def get_suggestions():
    try:
        # Retrieve per-user data
        user = get_user_data()
        df = user.get("df")

        if df is None:
            return jsonify({"success": False, "error": "No CSV uploaded yet."})

        title = request.form.get("title")
        if not title or title not in df["Title"].values:
            return jsonify({"success": False, "error": "Invalid title"})
    except Exception as e:
        return jsonify({"success": False, "error": f"Failed to get suggestions: {str(e)}"})

    row = df[df["Title"] == title].iloc[0]

    # Ensure Important Words exist
    iw_value = row.get("Important Words")
    if not iw_value or (isinstance(iw_value, float) and pd.isna(iw_value)) or (isinstance(iw_value, str) and not iw_value.strip()):
        desc_text = row["Description"]
        computed = important_words_from_texts([desc_text])
        iw_string = computed[0] if computed else ""
        df.loc[df["Title"] == title, "Important Words"] = iw_string
        iw_value = iw_string

        # Save updated DataFrame back to cache
        save_user_data({"df": df})

    words = (iw_value or "").split()

    # Generate n-grams
    one_word = generate_ngrams(words, n=1)
    two_word = generate_ngrams(words, n=2)
    one_word_podcasts = generate_ngrams(words, n=1, append_label="podcasts")
    two_word_podcasts = generate_ngrams(words, n=2, append_label="podcasts")

    one_word_text, two_word_text = generate_podcast_strings_for_keywordplanner(
        one_word, two_word, red_one_word=one_word_list, red_two_word=two_word_list
    )

    # Render partial templates
    suggestions_and_planner_HTML = render_template(
        "partials/suggestions_and_planner.html",
        selected_title=title,
        one_word=one_word,
        two_word=two_word,
        one_word_podcasts=one_word_podcasts,
        two_word_podcasts=two_word_podcasts,
        red_one_word=one_word_list, 
        red_two_word=two_word_list,
        yellow_one_word=synonym_for_one_word,
        yellow_two_word=synonym_for_two_word,
        one_word_podcast_text=one_word_text,
        two_word_podcast_text=two_word_text
    )

    return jsonify({"success": True, "html": suggestions_and_planner_HTML})







# MARK EPISODE ANALYZED
@app.route("/mark_episode_analyzed", methods=["POST"])
def mark_episode_analyzed():
    user = get_user_data()
    df = user.get("df")

    if df is None:
        return jsonify({"success": False, "error": "No CSV uploaded yet."}), 400

    data = request.get_json() or {}
    title = data.get("title")
    explicit_value = data.get("value")

    if title not in df["Title"].values:
        return jsonify({"success": False, "error": "Invalid title"}), 400

    # Toggle if explicit value not provided
    if explicit_value is None:
        current = bool(df.loc[df["Title"] == title, "Analyzed"].values[0])
        new_val = not current
    else:
        new_val = bool(explicit_value)

    df.loc[df["Title"] == title, "Analyzed"] = new_val

    # Save updated DataFrame back to cache
    save_user_data({"df": df})

    return jsonify({"success": True, "Analyzed": new_val})




# ADD QUERY
@app.route("/add_query", methods=["POST"])
def add_query():
    # Retrieve per-user data
    user = get_user_data()
    df = user.get("df")

    if df is None:
        return jsonify({"success": False, "error": "No CSV uploaded yet."}), 400

    data = request.get_json() or {}
    title = (data.get("title") or "").strip()
    query = (data.get("query") or "").strip()

    if not title or not query or title not in df["Title"].values:
        return jsonify({"success": False, "error": "Invalid title or query"}), 400

    # Ensure tracking columns exist
    if "No of Queries" not in df.columns:
        df["No of Queries"] = 0
    if "Added Queries" not in df.columns:
        df["Added Queries"] = ""

    existing_raw = df.loc[df["Title"] == title, "Added Queries"].values[0]

    # Coerce NaN / non-string to safe string
    if isinstance(existing_raw, float) and pd.isna(existing_raw):
        existing_raw = ""
    if not isinstance(existing_raw, str):
        existing_raw = str(existing_raw) if existing_raw is not None else ""

    items = [q for q in (s.strip() for s in existing_raw.split(",")) if q]
    if query not in items:
        items.append(query)

    # Update DataFrame
    df.loc[df["Title"] == title, "Added Queries"] = ",".join(items)
    df.loc[df["Title"] == title, "No of Queries"] = len(items)

    # Save updated DataFrame back to cache
    save_user_data({"df": df})

    return jsonify({"success": True, "saved_count": len(items), "saved_queries": items})



# REMOVE QUERY
@app.route("/remove_query", methods=["POST"])
def remove_query():
    # Retrieve per-user data
    user = get_user_data()
    df = user.get("df")

    if df is None:
        return jsonify({"success": False, "error": "No CSV uploaded yet."}), 400

    data = request.get_json() or {}
    title = (data.get("title") or "").strip()
    query = (data.get("query") or "").strip()

    if not title or not query or title not in df["Title"].values:
        return jsonify({"success": False, "error": "Invalid title or query"}), 400

    existing_raw = df.loc[df["Title"] == title, "Added Queries"].values[0]

    # Coerce NaN / non-string to safe string
    if isinstance(existing_raw, float) and pd.isna(existing_raw):
        existing_raw = ""
    if not isinstance(existing_raw, str):
        existing_raw = str(existing_raw) if existing_raw is not None else ""

    items = [q for q in (s.strip() for s in existing_raw.split(",")) if q]
    # Remove the query
    items = [q for q in items if q != query]

    # Update DataFrame
    df.loc[df["Title"] == title, "Added Queries"] = ",".join(items)
    df.loc[df["Title"] == title, "No of Queries"] = len(items)

    # Save updated DataFrame back to cache
    save_user_data({"df": df})

    return jsonify({"success": True, "saved_count": len(items), "saved_queries": items})



# GET EPISODE STATUS
@app.route("/get_episode_status")
def get_episode_status():
    # Retrieve per-user data
    user = get_user_data()
    df = user.get("df")

    if df is None:
        return jsonify({"Analyzed": False, "saved_count": 0, "saved_queries": []})

    title = request.args.get("title")
    if not title or title not in df["Title"].values:
        return jsonify({"Analyzed": False, "saved_count": 0, "saved_queries": []})

    row = df[df["Title"] == title].iloc[0]

    # Get raw value and guard against NaN / non-string
    existing_raw = row.get("Added Queries", "")
    if isinstance(existing_raw, float) and pd.isna(existing_raw):
        existing_raw = ""
    if not isinstance(existing_raw, str):
        existing_raw = str(existing_raw) if existing_raw is not None else ""

    # Build list of trimmed non-empty queries
    items = [q for q in (s.strip() for s in existing_raw.split(",")) if q]

    return jsonify({
        "Analyzed": bool(row.get("Analyzed", False)),
        "saved_count": len(items),
        "saved_queries": items
    })


# GET ANALYSIS STATUS OVERVIEW
@app.route("/get_analysis_status")
def get_analysis_status():
    # Retrieve per-user data
    user = get_user_data()
    df = user.get("df")

    if df is None:
        return jsonify({"error": "No data available"}), 400

    # Get analyzed and not analyzed episode indices
    analyzed_indices = df.index[df.get("Analyzed", False) == True].tolist()
    not_analyzed_indices = df.index[df.get("Analyzed", False) == False].tolist()

    # Convert 0-based indices to 1-based for display
    analyzed_episodes = [str(i + 1) for i in analyzed_indices]
    not_analyzed_episodes = [str(i + 1) for i in not_analyzed_indices]

    return jsonify({
        "analyzed_episodes": analyzed_episodes,
        "not_analyzed_episodes": not_analyzed_episodes,
        "total_episodes": len(df),
        "analyzed_count": len(analyzed_episodes),
        "not_analyzed_count": len(not_analyzed_episodes)
    })





# DOWNLOAD
@app.route("/download", methods=["GET"])
def download():
    # Retrieve per-user data
    user = get_user_data()
    df = user.get("df")
    uploaded_filename = user.get("uploaded_filename")

    if df is None or uploaded_filename is None:
        return redirect(url_for("home"))

    # Count processed and pending rows
    true_count = df["Analyzed"].sum() if "Analyzed" in df.columns else 0
    false_count = len(df) - true_count

    # Remove any existing "_<num>_rows_processed_<num>_pending" pattern
    base_name = uploaded_filename.rsplit(".", 1)[0]
    base_name = re.sub(r"_\d+_rows_processed_\d+_rows_pending$", "", base_name)

    # Create new descriptive name
    download_name = f"{base_name}_{true_count}_rows_processed_{false_count}_rows_pending.csv"

    # Prepare CSV for download
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    csv_buffer.seek(0)

    return Response(
        csv_buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={download_name}"}
    )








# RUN APP
if __name__ == "__main__":
    app.run(debug=True, threaded=True)
