# Deploying to Render

## Required: Database URL

The backend **must** have `DATABASE_URL` set to your **Render PostgreSQL** connection string.  
If it is missing or points to `localhost`, you will see:

```text
ConnectionRefusedError: [Errno 111] Connection refused
```

### Steps

1. In [Render Dashboard](https://dashboard.render.com), open your **PostgreSQL** instance.
2. Copy the **Internal Database URL** (use this for services in the same Render account).
3. Open your **Web Service** (the backend API).
4. Go to **Environment**.
5. Add or edit:
   - **Key:** `DATABASE_URL`
   - **Value:** the Internal Database URL you copied (e.g. `postgresql://user:pass@host/dbname`).
6. Save. Render will redeploy; the app will then connect to the database.

Do not commit the actual URL or password to git. Set it only in Render's Environment.
