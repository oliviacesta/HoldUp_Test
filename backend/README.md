# HoldUp Backend: Setup & Local Testing Guide

This guide covers how to set up, run, and expose the **HoldUp** backend API locally for development and testing.

---

## 1. Prerequisites (Core Tools)
Ensure you have the following installed on your system before proceeding:
* **Python**: `v3.10` or higher (`python3 --version`)
* **Node.js**: `v18` or higher (`node -v`)
* **Git**: (`git --version`)

---

## 2. Local App Setup

### Step 1: Clone and Navigate
Clone the repository and navigate into the backend directory:
```bash
git clone https://github.com/oliviacesta/HoldUp_Test.git
cd HoldUp_Test/backend
```

### Step 2: Create a Virtual Environment
Set up an isolated Python virtual environment:
```bash
python3 -m venv venv
```

### Step 3: Activate the Virtual Environment
Activate the environment depending on your operating system:
* **macOS / Linux:**
  ```bash
  source venv/bin/activate
  ```
* **Windows (Command Prompt / PowerShell):**
  ```cmd
  venv\Scripts\activate
  ```

### Step 4: Install Dependencies
Install the required Python packages inside your active virtual environment:
```bash
python -m pip install -r requirements.txt
```

### Step 5: Configure Environment Variables
Create a file named `.env` inside the `backend` folder and add your Supabase database connection string. 
> ⚠️ **Important:** Ensure `?statement_cache_size=0` is appended to the end of the URL to prevent caching errors with Supabase's pooler.

```env
DATABASE_URL=postgresql://postgres.your-project-ref:your-db-password@aws-1-ca-central-1.pooler.supabase.com:6543/postgres?statement_cache_size=0
```

---

## 3. Running the Server

Start your FastAPI development server locally with auto-reload enabled:
```bash
uvicorn main:app --reload
```

* **Test the API:** Open your browser and navigate to **`http://127.0.0.1:8000/docs`** to interact with the Swagger UI and test endpoints like creating holds and inventory items.

---

## 4. Local Testing with Ngrok (Optional)

If you need to test your backend from a mobile device (like a React Native/Expo app) or over the public internet while running locally, you can use **Ngrok**:

1. Sign up/in at [ngrok Dashboard](https://dashboard.ngrok.com/get-started/share-localhost) using GitHub.
2. Install Ngrok (e.g., on macOS via Homebrew):
   ```bash
   brew install ngrok
   ```
3. Add your authtoken to your local ngrok configuration:
   ```bash
   ngrok config add-authtoken YOUR_AUTHTOKEN
   ```
4. With your FastAPI server running, expose port `8000` to the internet:
   ```bash
   ngrok http 8000
   ```
5. Copy the public forwarding URL provided in your terminal output and use it as your frontend's API endpoint.

---


may also need to do brew install supabase/tap/supabase
then: supabase login
supabase link --project-ref ddawfvvrqemgzrnajtje


## 💡 Note on Hosting Limitations & Production
* **Current Limitation:** Right now, your local computer hosts the endpoints. The API will work across the internet via Ngrok, but **if your computer goes to sleep or turns off, the API goes offline**.
* **Final Product Solution:** For production, this backend will be deployed to a cloud-hosted PaaS provider (such as Render, Railway, or Fly.io) to ensure 24/7 availability with a permanent public URL.