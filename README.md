# Import your IMDb watchlist and ratings to your [JustWatch](https://www.justwatch.com) account

This script helps you import your IMDb watchlist and ratings (as a seenlist) into your JustWatch account.


### Prerequisites:
*   An IMDb account (where your watchlist and ratings are).
*   A JustWatch account (where you want to import your lists).
*   Python 3.7 or newer. If you don't have it, installing `uv` (see below) can help manage Python installations.
*   **`uv` (Recommended for Setup):** A fast Python project and virtual environment manager. Installation instructions: [uv documentation](https://docs.astral.sh/uv/getting-started/installation/). `uv` can create the virtual environment and install all dependencies for you.
*   Git (a tool for downloading code from services like GitHub).


### Setup:

1.  **Get the Script Files (Clone the Repository):**
    Open a terminal or command prompt and run:
    ```bash
    git clone https://github.com/vinismarques/imdb-to-justwatch
    cd imdb-to-justwatch # Go into the folder that was created
    ```

2.  **Set up Virtual Environment and Install Dependencies (using `uv`):**
    `uv` will automatically create a virtual environment (usually named `.venv` in the project folder) if it doesn't exist, and then install the required packages into it.

    In your terminal, from the `imdb-to-justwatch` project directory, run:
    ```bash
    uv sync
    ```
    This command reads the project's dependency file (`pyproject.toml`), sets up the isolated environment, and installs everything needed.

    **(Optional) To activate the virtual environment created by `uv` (if you need to run other commands or check things manually):**
    *   **On macOS and Linux:**
        ```bash
        source .venv/bin/activate
        ```
    *   **On Windows (Command Prompt):**
        ```cmd
        .venv\Scripts\activate
        ```
    *   **On Windows (PowerShell):**
        ```powershell
        .venv\Scripts\Activate.ps1
        ```
    You should see `(.venv)` at the beginning of your command line prompt.
    *(Note: For running the main import scripts, direct activation might not be strictly necessary if you always preface python commands with `uv python ...`, but it's good practice to activate it for a development session.)*

3.  **Prepare Your IMDb Export Files:**
    You need to download two files from your IMDb account: one for your watchlist and one for your ratings (which we'll use as a "seenlist").

    *   **Create an `exports/` Folder:**
        Inside your project folder (the one containing the scripts), create a new folder named `exports`. This is where you'll save the files from IMDb.

    *   **Download Your IMDb Watchlist:**
        a.  Go to your IMDb Watchlist page (you can usually find this by logging into IMDb, clicking your profile name, and selecting "Your Watchlist").
        b.  Scroll all the way to the bottom of your watchlist page.
        c.  Click the "Export this list" link.
        d.  Save the downloaded file directly into the `exports/` folder you created.
        e.  **Crucially, rename this file to `watchlist.csv`**.

    *   **Download Your IMDb Ratings (for Seenlist):**
        a.  Go to your IMDb Ratings page (log into IMDb, click your profile name, then "Your Ratings").
        b.  Look for a menu with three dots (⋮) or an "options" button, usually near the top of the ratings list. Click it.
        c.  Select "Export" from the menu.
        d.  Save the downloaded file directly into the `exports/` folder.
        e.  **Crucially, rename this file to `ratings.csv`**.

    After these steps, your `exports/` folder should contain `watchlist.csv` and `ratings.csv`.

4.  **Get Your JustWatch Authorization Token:**
    This token allows the script to act on your behalf on JustWatch (like adding movies to your lists).

    *   Open your web browser (like Chrome, Firefox, or Edge).
    *   Go to [JustWatch](https://www.justwatch.com/) and log in to your account.
    *   Open your browser's **Developer Tools**. You can usually do this by:
        *   Pressing the `F12` key.
        *   Right-clicking anywhere on the JustWatch page and selecting "Inspect" or "Inspect Element".
    *   In the Developer Tools panel that appears, find and click on the **"Network"** tab.
    *   Now, perform an action on the JustWatch website that requires you to be logged in. For example, add any movie to your JustWatch watchlist or mark a movie as "seen". This will make your browser send a request that includes your authorization token.
    *   In the Network tab, you'll see a list of requests. Look for entries that start with `graphql` (you might see `graphql?operationName=...`). You can use the filter bar in the Network tab to search for "graphql".
    *   Click on one of these `graphql` entries.
    *   A new panel will show details for that request. Look for a section called **"Request Headers"** (or similar, like "Headers" then "Request Headers").
    *   Inside Request Headers, find the line that says `Authorization`. The value next to it will start with `Bearer ` followed by a long string of characters (e.g., `Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...`).
    *   **Copy this entire value**, including the `Bearer ` part and all the characters after it. This is your authorization token.

5.  **Tell the Script Your Authorization Token (Using an Environment Variable):**
    The script needs to know your token. The most secure way to provide it is by setting it as an "environment variable". This is like a temporary note for your computer that the script can read.

    You'll need to do this in the same terminal or command prompt window where you activated the virtual environment and will run the scripts. This setting is usually temporary and only lasts for your current terminal session.

    *   **On macOS or Linux:**
        Replace `Bearer eyJ...your...token...here` with the actual token you copied.
        ```bash
        export JUSTWATCH_AUTH_TOKEN="Bearer eyJ...your...token...here"
        ```
    *   **On Windows (Command Prompt):**
        Replace `Bearer eyJ...your...token...here` with the actual token you copied.
        ```cmd
        set JUSTWATCH_AUTH_TOKEN=Bearer eyJ...your...token...here
        ```
    *   **On Windows (PowerShell):**
        Replace `Bearer eyJ...your...token...here` with the actual token you copied.
        ```powershell
        $env:JUSTWATCH_AUTH_TOKEN="Bearer eyJ...your...token...here"
        ```
    Make sure there are no extra spaces around the `=` sign or inside the quotes. If your token has special characters, keeping it inside the quotes is important.


### Running the Importers:

Make sure you have:
1.  The virtual environment active (e.g., `(.venv)` is in your prompt if you activated it manually) OR you are using `uv` to run the scripts (see below).
2.  Placed your `watchlist.csv` and/or `ratings.csv` in the `exports/` folder.
3.  Set the `JUSTWATCH_AUTH_TOKEN` environment variable in your current terminal session.

*   **To import your IMDb Watchlist to JustWatch:**
    Run the following command in your terminal (from the `imdb-to-justwatch` directory):
    ```bash
    uv run import_watchlist.py
    ```
    (If you have the `.venv` activated manually, `python import_watchlist.py` will also work).

*   **To import your IMDb Ratings (as a Seenlist) to JustWatch:**
    Run the following command in your terminal (from the `imdb-to-justwatch` directory):
    ```bash
    uv run import_seenlist.py
    ```
    (If you have the `.venv` activated manually, `python import_seenlist.py` will also work).

The scripts will show progress and log any issues they encounter.


### Notes:
*   The scripts have a built-in delay between actions to be kind to the JustWatch servers and avoid being blocked.
*   **API Usage:** The JustWatch APIs used by this script are internal. While generally safe for personal, limited use (like importing your lists), they are not officially public or documented for third-party commercial use. Please use responsibly.
*   Websites like IMDb and JustWatch sometimes change how their pages or export files are structured. If the scripts stop working, it might be because of such a change. In that case, parts of the script (like column numbers or API details) might need to be updated.
*   **Keep your `JUSTWATCH_AUTH_TOKEN` private!** It's like a password for your JustWatch account. Don't share it publicly. The environment variable method helps keep it more secure than typing it directly into the script.
*   **Inspiration:** This project was inspired by the work done by @prasanth-G24 in the [Imdb_to_JustWatch](https://github.com/prasanth-G24/Imdb_to_JustWatch) repository.
