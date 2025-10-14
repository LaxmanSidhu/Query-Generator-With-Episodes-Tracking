from flask import Flask, render_template, request, redirect, url_for, Response, jsonify
import pandas as pd
import io
import threading
import time
from helper import important_words_from_texts, generate_ngrams, generate_podcast_strings_for_keywordplanner
from queries_list import one_word_list, two_word_list, synonym_for_one_word, synonym_for_two_word

app = Flask(__name__)


# Global variables
df_global = None
uploaded_filename = None
current_csv_file = None
processing_state = {
    "in_progress": False,
    "started_at": None,
    "percent": 0,
    "eta": "00:00:00",
    "done": False
}



# HOME PAGE
@app.route("/", methods=["GET", "POST"])
def home():
    global df_global, uploaded_filename, current_csv_file
    message = None
    table_html = None

    if request.method == "POST":
        file = request.files.get("file")
        if file and file.filename.endswith(".csv"):
            uploaded_filename = file.filename
            df_global = pd.read_csv(file)
            current_csv_file = uploaded_filename  # temporary storage

            # Validate required columns
            if "Title" not in df_global.columns or "Description" not in df_global.columns:
                df_global = None
                uploaded_filename = None
                message = "CSV must contain columns: Title, Description"
                return render_template("home.html", rows=None, cols=None, filename=None, message=message, table=None)

            # Column handling rules:
            # - If CSV has only Title and Description, add 3 new columns with defaults
            # - If it has 3+ columns, preserve provided values; only add missing required columns with defaults
            existing_cols = set(df_global.columns)
            required_defaults = {
                "Analyzed": False,
                "No of Queries": 0,
                "Added Queries": ""
            }
            # Only add the three tracking columns if missing; do not create important_words here
            for col, default_val in required_defaults.items():
                if col not in existing_cols:
                    df_global[col] = default_val

            message = "CSV uploaded successfully. Click 'Generate Important Queries' to continue."

    # If a CSV is already uploaded, render the table
    if df_global is not None:
        table_html = df_global.to_html(classes="table table-striped", index=False)

    rows = df_global.shape[0] if df_global is not None else None
    cols = df_global.shape[1] if df_global is not None else None

    return render_template("home.html",
                           rows=rows,
                           cols=cols,
                           filename=uploaded_filename,
                           message=message,
                           table=table_html)




# BACKGROUND PROCESSING
def process_important_words():
    global df_global, processing_state
    total_rows = len(df_global)
    batch_size = 10
    important_words_list = []

    processing_state["in_progress"] = True
    processing_state["started_at"] = time.time()
    processing_state["percent"] = 0
    processing_state["eta"] = "00:00:00"
    processing_state["done"] = False

    for start in range(0, total_rows, batch_size):
        end = min(start + batch_size, total_rows)
        batch_texts = df_global["Description"].iloc[start:end].tolist()
        batch_words = important_words_from_texts(batch_texts)
        important_words_list.extend(batch_words)
        # progress & ETA
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
        time.sleep(0.001)  # small delay

    df_global["Important Words"] = important_words_list
    processing_state["percent"] = 100
    processing_state["eta"] = "00:00:00"
    processing_state["done"] = True
    processing_state["in_progress"] = False





# START PROCESSING
@app.route("/process", methods=["POST"])
def process():
    global df_global, processing_state

    if df_global is None:
        return jsonify({"status": "no_csv_uploaded"}), 400
    
    # If already processed (has important_words with any non-null), just redirect to results
    if "Important Words" in df_global.columns and df_global["Important Words"].notna().any():
        return jsonify({"status": "already_processed", "redirect": url_for("results")})

    # If already running, just acknowledge
    if processing_state.get("in_progress") and not processing_state.get("done"):
        return jsonify({"status": "already_running"})

    # Reset state and start async processing
    processing_state.update({
        "in_progress": True,
        "started_at": time.time(),
        "percent": 0,
        "eta": "00:00:00",
        "done": False
    })
    thread = threading.Thread(target=process_important_words, daemon=True)
    thread.start()
    return jsonify({"status": "started"})





# PROGRESS POLLING
@app.route("/progress", methods=["GET"])
def progress():
    global processing_state
    return jsonify({
        "in_progress": bool(processing_state.get("in_progress", False)),
        "percent": int(processing_state.get("percent", 0)),
        "eta": processing_state.get("eta", "00:00:00"),
        "done": bool(processing_state.get("done", False))
    })






# RESULTS PAGE - FULL PAGE
@app.route("/results", methods=["GET", "POST"])
def results():
    global df_global
    if df_global is None:
        return render_template(
            "results.html",
            message="Processing not done yet. Please upload a CSV first.",
            download_ready=False,
            analyzed_count=0,
            total_episodes=0
        )

    # Compute analyzed and total counts
    try:
        analyzed_count = int(df_global["Analyzed"].sum()) if "Analyzed" in df_global.columns else 0
    except Exception:
        analyzed_count = 0
    total_episodes = int(df_global.shape[0])

    # POST: when user clicks "Get Suggestions" button
    if request.method == "POST":
        title = request.form.get("title")
        if not title or title not in df_global["Title"].values:
            return render_template(
                "results.html",
                titles=df_global["Title"].tolist(),
                download_ready=("Important Words" in df_global.columns),
                analyzed_count=analyzed_count,
                total_episodes=total_episodes
            )

        row = df_global[df_global["Title"] == title].iloc[0]

        # Ensure important words exist for this episode
        iw_value = row.get("Important Words") if isinstance(row, dict) else row["Important Words"]
        if not iw_value or (isinstance(iw_value, float) and pd.isna(iw_value)) or (isinstance(iw_value, str) and not iw_value.strip()):
            desc_text = row["Description"]
            computed = important_words_from_texts([desc_text])
            iw_string = computed[0] if isinstance(computed, (list, tuple)) and computed else ""
            df_global.loc[df_global["Title"] == title, "Important Words"] = iw_string
            iw_value = iw_string

        words = (iw_value or "").split()

        one_word = generate_ngrams(words, n=1)
        two_word = generate_ngrams(words, n=2)
        one_word_podcasts = generate_ngrams(words, n=1, append_label="podcasts")
        two_word_podcasts = generate_ngrams(words, n=2, append_label="podcasts")

        one_word_text, two_word_text = generate_podcast_strings_for_keywordplanner(
            one_word, two_word, red_one_word=one_word_list, red_two_word=two_word_list
        )

        titles_with_index = [(i + 1, t) for i, t in enumerate(df_global["Title"].tolist())]
        true_count = df_global['Analyzed'].sum()

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
        titles=df_global["Title"].tolist(),
        download_ready=("Important Words" in df_global.columns),
        analyzed_count=analyzed_count,
        total_episodes=total_episodes
    )



@app.route("/get_suggestions", methods=["POST"])
def get_suggestions():
    global df_global
    if df_global is None:
        return jsonify({"success": False, "error": "No CSV uploaded yet."})

    title = request.form.get("title")
    if not title or title not in df_global["Title"].values:
        return jsonify({"success": False, "error": "Invalid title"})

    row = df_global[df_global["Title"] == title].iloc[0]

    # Ensure Important Words exist
    iw_value = row.get("Important Words")
    if not iw_value or (isinstance(iw_value, float) and pd.isna(iw_value)) or (isinstance(iw_value, str) and not iw_value.strip()):
        desc_text = row["Description"]
        computed = important_words_from_texts([desc_text])
        iw_string = computed[0] if computed else ""
        df_global.loc[df_global["Title"] == title, "Important Words"] = iw_string
        iw_value = iw_string

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
    global df_global
    data = request.get_json() or {}
    title = data.get("title")

    # Optional explicit value; if not provided, toggle
    explicit_value = data.get("value")
    if title not in df_global["Title"].values:
        return jsonify({"success": False}), 400

    if explicit_value is None:
        current = bool(df_global.loc[df_global["Title"] == title, "Analyzed"].values[0])
        new_val = not current
    else:
        new_val = bool(explicit_value)

    df_global.loc[df_global["Title"] == title, "Analyzed"] = new_val
    
    return jsonify({"success": True, "Analyzed": new_val})




# ADD QUERY
@app.route("/add_query", methods=["POST"])
def add_query():
    global df_global
    data = request.get_json() or {}
    title = (data.get("title") or "").strip()
    query = (data.get("query") or "").strip()

    if not title or not query or title not in df_global["Title"].values:
        return jsonify({"success": False}), 400

    if "No of Queries" not in df_global.columns:
        df_global["No of Queries"] = 0
    if "Added Queries" not in df_global.columns:
        df_global["Added Queries"] = ""

    existing_raw = df_global.loc[df_global["Title"] == title, "Added Queries"].values[0]
    # Coerce NaN / non-string to a safe string before splitting
    try:
        import pandas as pd  # local import to ensure availability in route context
        if isinstance(existing_raw, float) and pd.isna(existing_raw):
            existing_raw = ""
    except Exception:
        if isinstance(existing_raw, float):
            existing_raw = ""
    if not isinstance(existing_raw, str):
        existing_raw = str(existing_raw) if existing_raw is not None else ""

    items = [q for q in (s.strip() for s in existing_raw.split(",")) if q]
    if query not in items:
        items.append(query)
    df_global.loc[df_global["Title"] == title, "Added Queries"] = ",".join(items)
    df_global.loc[df_global["Title"] == title, "No of Queries"] = len(items)

    return jsonify({"success": True, "saved_count": len(items), "saved_queries": items})





# REMOVE QUERY
@app.route("/remove_query", methods=["POST"])
def remove_query():
    global df_global
    data = request.get_json() or {}
    title = (data.get("title") or "").strip()
    query = (data.get("query") or "").strip()
    if not title or not query or title not in df_global["Title"].values:
        return jsonify({"success": False}), 400

    existing_raw = df_global.loc[df_global["Title"] == title, "Added Queries"].values[0]
    # Coerce NaN / non-string to a safe string before splitting
    try:
        import pandas as pd  # local import to ensure availability in route context
        if isinstance(existing_raw, float) and pd.isna(existing_raw):
            existing_raw = ""
    except Exception:
        if isinstance(existing_raw, float):
            existing_raw = ""
    if not isinstance(existing_raw, str):
        existing_raw = str(existing_raw) if existing_raw is not None else ""

    items = [q for q in (s.strip() for s in existing_raw.split(",")) if q]
    items = [q for q in items if q != query]
    df_global.loc[df_global["Title"] == title, "Added Queries"] = ",".join(items)
    df_global.loc[df_global["Title"] == title, "No of Queries"] = len(items)

    return jsonify({"success": True, "saved_count": len(items), "saved_queries": items})





# GET EPISODE STATUS
@app.route("/get_episode_status")
def get_episode_status():
    global df_global
    title = request.args.get("title")
    if title not in df_global["Title"].values:
        return jsonify({"Analyzed": False, "saved_count": 0, "saved_queries": []})

    row = df_global[df_global["Title"] == title].iloc[0]

    # Get raw value and guard against NaN / non-string
    existing_raw = row.get("Added Queries", "")
    # If pandas gives NaN (a float), convert to empty string
    try:
        # pandas NaN check
        import pandas as pd
        if isinstance(existing_raw, float) and pd.isna(existing_raw):
            existing_raw = ""
    except Exception:
        # fallback: if it's float and not usable, make it empty
        if isinstance(existing_raw, float):
            existing_raw = ""

    # Ensure we have a string to split
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
    global df_global
    if df_global is None:
        return jsonify({"error": "No data available"}), 400
    
    # Get analyzed and not analyzed episode indices
    analyzed_indices = df_global.index[df_global["Analyzed"] == True].tolist()
    not_analyzed_indices = df_global.index[df_global["Analyzed"] == False].tolist()
    
    # Convert 0-based indices to 1-based for display
    analyzed_episodes = [str(i + 1) for i in analyzed_indices]
    not_analyzed_episodes = [str(i + 1) for i in not_analyzed_indices]
    
    return jsonify({
        "analyzed_episodes": analyzed_episodes,
        "not_analyzed_episodes": not_analyzed_episodes,
        "total_episodes": len(df_global),
        "analyzed_count": len(analyzed_episodes),
        "not_analyzed_count": len(not_analyzed_episodes)
    })






# DOWNLOAD
@app.route("/download", methods=["GET"])
def download():
    import re
    import io
    from flask import Response, redirect, url_for

    global df_global, uploaded_filename

    if df_global is None:
        return redirect(url_for("home"))

    # Count processed and pending rows
    true_count = df_global["Analyzed"].sum()                # True values
    false_count = len(df_global) - true_count               # False values

    # Remove any existing "_<num>_rows_processed_<num>_pending" pattern
    base_name = uploaded_filename.rsplit(".", 1)[0]
    base_name = re.sub(r"_\d+_rows_processed_\d+_rows_pending$", "", base_name)

    # Create new descriptive name
    download_name = f"{base_name}_{true_count}_rows_processed_{false_count}_rows_pending.csv"

    # Prepare CSV for download
    csv_buffer = io.StringIO()
    df_global.to_csv(csv_buffer, index=False)
    csv_buffer.seek(0)

    return Response(
        csv_buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={download_name}"}
    )









# RUN APP
if __name__ == "__main__":
    app.run(debug=True, threaded=True)
