# Free Deployment Guide (No Docker Required)

This guide will help you deploy both frontend (Streamlit) and backend (FastAPI) for free without Docker.

## Option 1: Streamlit Community Cloud + Render (Recommended)

### Frontend: Streamlit Community Cloud (Free)

1. **Push your code to GitHub** (if not already done)
   ```bash
   git add .
   git commit -m "Prepare for deployment"
   git push origin main
   ```

2. **Deploy to Streamlit Community Cloud:**
   - Go to https://share.streamlit.io/
   - Sign in with GitHub
   - Click "New app"
   - Select your repository
   - Main file path: `streamlit_app.py`
   - Click "Deploy"
   - Your app will be live at: `https://your-app-name.streamlit.app`

3. **Set Environment Variables in Streamlit Cloud:**
   - Go to your app settings
   - Click "Secrets" → "Edit secrets"
   - Add:
     ```toml
     API_BASE_URL = "https://your-backend-url.onrender.com"
     ```

### Backend: Render (Free Tier)

1. **Create a Render account:** https://render.com (Sign up with GitHub)

2. **Create a new Web Service:**
   - Click "New +" → "Web Service"
   - Connect your GitHub repository
   - Configure:
     - **Name:** `msc-chatbot-backend` (or any name)
     - **Environment:** `Python 3`
     - **Build Command:** `pip install -r requirements.txt`
     - **Start Command:** `python main.py`
     - **Plan:** Free

3. **Set Environment Variables in Render:**
   - Go to your service → Environment
   - Add these variables:
     ```
     AWS_ACCESS_KEY_ID=your_aws_key
     AWS_SECRET_ACCESS_KEY=your_aws_secret
     AWS_DEFAULT_REGION=us-east-1
     MONGODB_URI=your_mongodb_uri
     MONGODB_DATABASE=msc-chatbot
     BEDROCK_MODEL_ID=mistral.mistral-large-2402-v1:0
     BEDROCK_KNOWLEDGE_BASE_ID=your_kb_id
     ENVIRONMENT=production
     ```

4. **Update CORS in backend:**
   - After deployment, you'll get a URL like: `https://msc-chatbot-backend.onrender.com`
   - Update `src/api/routes.py` to allow your Streamlit URL:
     ```python
     allowed_origins = [
         "https://your-app-name.streamlit.app",
         "https://*.streamlit.app",  # Allow all Streamlit apps
     ]
     ```

5. **Deploy:**
   - Click "Create Web Service"
   - Wait for deployment (5-10 minutes first time)
   - Your backend will be at: `https://your-service-name.onrender.com`

6. **Update Streamlit secrets:**
   - Go back to Streamlit Cloud → Secrets
   - Update `API_BASE_URL` to your Render backend URL

---

## Option 2: Railway (All-in-One)

Railway can host both, but you'll need separate services.

1. **Sign up:** https://railway.app (GitHub login)

2. **Deploy Backend:**
   - New Project → Deploy from GitHub
   - Select your repo
   - Add service → Select repo
   - Settings:
     - **Start Command:** `python main.py`
     - **Port:** 8502 (Railway auto-assigns, use `$PORT` env var)
   - Add environment variables (same as Render)
   - Deploy

3. **Deploy Frontend:**
   - Add another service in same project
   - Settings:
     - **Start Command:** `streamlit run streamlit_app.py --server.port $PORT --server.address 0.0.0.0`
   - Add environment variable: `API_BASE_URL=https://your-backend-url.railway.app`
   - Deploy

---

## Option 3: Fly.io (Free Tier)

1. **Install Fly CLI:**
   ```bash
   curl -L https://fly.io/install.sh | sh
   ```

2. **Deploy Backend:**
   ```bash
   fly launch --name msc-backend
   # Follow prompts, select Python
   # Set environment variables
   fly secrets set AWS_ACCESS_KEY_ID=your_key AWS_SECRET_ACCESS_KEY=your_secret ...
   fly deploy
   ```

3. **Deploy Frontend:**
   ```bash
   fly launch --name msc-frontend
   # Set API_BASE_URL secret
   fly secrets set API_BASE_URL=https://msc-backend.fly.dev
   fly deploy
   ```

---

## Quick Setup Scripts

### For Render Backend:

Create `render.yaml` (already created in repo) and use it, or manually configure as above.

### For Streamlit Cloud:

Just push to GitHub and deploy through the web interface - no config needed!

---

## Important Notes:

1. **Free tier limitations:**
   - Render: Services sleep after 15 min inactivity (wakes on first request)
   - Railway: $5 free credits/month
   - Fly.io: 3 shared VMs free

2. **Cold starts:**
   - First request after sleep may take 30-60 seconds
   - Tell your manager about this limitation

3. **Environment variables:**
   - Never commit `.env` file to GitHub
   - Use platform secrets/environment variables

4. **CORS:**
   - Make sure backend allows your frontend domain
   - Update `src/api/routes.py` with production URLs

---

## Testing Locally Before Deploying:

1. **Start backend:**
   ```bash
   python main.py
   ```

2. **Start frontend (in another terminal):**
   ```bash
   export API_BASE_URL=http://localhost:8502
   streamlit run streamlit_app.py
   ```

3. **Test the connection** - if it works locally, it should work deployed!

---

## Troubleshooting:

- **Backend not responding:** Check Render/Railway logs
- **CORS errors:** Update allowed origins in `src/api/routes.py`
- **Environment variables:** Double-check all are set correctly
- **Import errors:** Make sure `requirements.txt` has all dependencies

---

## Recommended: Streamlit Cloud + Render

This is the easiest and most reliable free option:
- ✅ Streamlit Cloud: Zero config, just connect GitHub
- ✅ Render: Simple Python deployment, free tier available
- ✅ Both have good documentation
- ✅ Easy to update (just push to GitHub)
