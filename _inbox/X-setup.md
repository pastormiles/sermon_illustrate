# Twitter/X Integration Setup for Sermon IllustrAIt

Follow these steps to connect Twitter/X to your Sermon IllustrAIt app.

---

## Step 1: Create a Twitter Account (if needed)

Create **@sermonillustrAIte** or use your existing account at https://twitter.com

---

## Step 2: Apply for Developer Access

1. Go to **https://developer.twitter.com**
2. Click **"Sign up for Free Account"** (or log in with your Twitter account)
3. Accept the Developer Agreement

---

## Step 3: Create a Project & App

1. In the Developer Portal, click **"Projects & Apps"** in the sidebar
2. Click **"+ Add Project"**
3. Name it: `Sermon IllustrAIt`
4. Select use case: **"Making a bot"** or **"Exploring the API"**
5. Name your app: `sermon-illustrait-app`

---

## Step 4: Set Up OAuth 2.0

1. In your app settings, go to **"User authentication settings"**
2. Click **"Set up"**
3. Configure the following:
   - **App permissions**: `Read` (read-only is sufficient)
   - **Type of App**: `Web App, Automated App or Bot`
   - **Callback URL**: `http://localhost:8000/auth/twitter/callback`
   - **Website URL**: `http://localhost:8000`
4. Click **Save**

---

## Step 5: Get Your Credentials

1. Go to the **"Keys and tokens"** tab
2. Under **OAuth 2.0 Client ID and Client Secret**, click **"Regenerate"**
3. Copy both values - you'll need them for the next step

---

## Step 6: Update Your .env File

Open `/Users/miles/Claude_Code/nomion_ai/sermon_illustrate/.env` and add your credentials:

```
TWITTER_CLIENT_ID=your_client_id_here
TWITTER_CLIENT_SECRET=your_client_secret_here
```

The callback URL is already configured:
```
TWITTER_CALLBACK_URL=http://localhost:8000/auth/twitter/callback
```

---

## Step 7: Restart & Connect

1. Restart the server:
   ```bash
   cd /Users/miles/Claude_Code/nomion_ai/sermon_illustrate
   source venv/bin/activate
   python -m src.main
   ```

2. Go to http://localhost:8000/settings

3. In the **X (Twitter) Integration** section, click **"Connect X Account"**

4. Authorize the app with your Twitter account

5. You're connected! You can now search Twitter for trending topics and sermon illustrations.

---

## Features Available After Setup

- **Twitter Search**: Search for tweets related to your sermon topics
- **Trending Topics**: See what's trending to find timely illustrations
- **Real-time Content**: Access current conversations and events

---

## Troubleshooting

**"Not configured" message in settings:**
- Make sure `TWITTER_CLIENT_ID` and `TWITTER_CLIENT_SECRET` are set in `.env`
- Restart the server after updating `.env`

**OAuth error during connection:**
- Verify your callback URL matches exactly: `http://localhost:8000/auth/twitter/callback`
- Check that your app has OAuth 2.0 enabled in Developer Portal

**API rate limits:**
- Free tier allows 1,500 tweet reads per month
- Trending topics don't count against this limit
