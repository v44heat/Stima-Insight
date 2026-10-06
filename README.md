# Stima Insight

**Machine Learning-Based Electricity Consumption Forecasting and Anomaly Detection System for Kenyan Households**

A web application that learns a household's normal electricity usage from its own history, forecasts what comes next, and flags hours where usage departs from the expected pattern. Built with React, Flask, PostgreSQL and scikit-learn / statsmodels.

> **Read this first:** the demo data in this project is **synthetic** (simulated). It is not real Kenya Power or household meter data, and the app labels it "Demo/Synthetic Data" everywhere it appears.

---

## 1. What you need to install

You need exactly **three programs**. Nothing else.

| Program | Version | Why |
| --- | --- | --- |
| **Python** | **3.11 or 3.12** | Runs the backend and the machine-learning code |
| **Node.js** | **LTS (20 or 22)** | Runs the React frontend |
| **PostgreSQL** | **14 to 17** (tested on 16) | The database |
---

### 2 Create the empty database

The app needs an empty database called `electricity_forecasting`. The easiest way is **pgAdmin**:

1. Open **pgAdmin 4** from the Start menu and enter your `postgres` password when asked.
2. In the left panel expand *Servers*, then *PostgreSQL 16*. Right-click **Databases**, choose **Create**, then **Database…**
3. Type `electricity_forecasting` as the name and click **Save**.

Prefer the command line? Open **SQL Shell (psql)** from the Start menu, press Enter at each prompt (Server, Database, Port, Username), type your password, then run:

```sql
CREATE DATABASE electricity_forecasting;
```


## 3. Set up the project

Unzip the project somewhere simple, for example `C:\projects\electricity-forecasting-system`. In File Explorer, open that folder, click the address bar, type `cmd` and press Enter. That opens a Command Prompt in the right place.

### 3.1 Backend packages

```bat
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

After the `activate` line your prompt starts with `(venv)`. That means the virtual environment is on. The `pip install` takes a few minutes the first time.

> **Using PowerShell instead of Command Prompt?** Activate with `.\venv\Scripts\Activate.ps1`. If PowerShell refuses to run scripts, run this once and try again: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

### 3.2 Create your `.env` file

```bat
copy .env.example .env
notepad .env
```

Notepad opens the file. It contains settings the app reads at startup:

- `DATABASE_URL`: how the app finds PostgreSQL. Replace `password` with **your** `postgres` password from step 2.3:

  ```
  DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/electricity_forecasting
  ```

  **If your password contains special characters, they must be written in "URL form"**, otherwise the connection fails. The common ones: `@` becomes `%40`, `#` becomes `%23`, `/` becomes `%2F`, `:` becomes `%3A`, `%` becomes `%25`, and a space becomes `%20`. The simplest fix is to pick a password with only letters and numbers.

- `SECRET_KEY` and `JWT_SECRET_KEY`: two long random strings used to sign login tokens. Do not leave the placeholder text. Generate each one by running this in the Command Prompt and pasting the result (run it twice, once per key):

  ```bat
  python -c "import secrets; print(secrets.token_hex(32))"
  ```

- `FLASK_ENV`: leave as `development` while you work.
- `FRONTEND_ORIGIN` and `MAX_UPLOAD_MB`: leave the defaults. (`MAX_UPLOAD_MB` is the largest CSV you can upload.)

Save and close Notepad. **Never share or upload your `.env` file.** The `.gitignore` already keeps it out of Git.

### 3.3 Create the tables, demo users and demo data

Still in the `backend` folder with `(venv)` showing:

```bat
python seed_database.py
```

This takes **one to three minutes** and does everything in order:

1. Creates all the tables.
2. Creates two accounts (listed in section 5).
3. Saves a default tariff and the default anomaly thresholds.
4. Creates a demo household.
5. Generates **synthetic** hourly data (180 days) and stores it.
6. Trains the forecasting models and runs anomaly detection.

When it finishes you will see `DEV/DEMO login` followed by the two logins. If you want to skip the training step (it can be done later in the app), use `python seed_database.py --no-train`.

### 3.4 Start the backend

```bat
python run.py
```

Leave this window **open**. The backend is now running at <http://127.0.0.1:5000>. To check it is alive, open <http://127.0.0.1:5000/api/auth/me> in a browser. Seeing a short error message that says `Authentication required` is the **correct** result: it means the server is up and protecting its data.

### 3.5 Start the frontend

Open a **second** Command Prompt window (the first must keep running), go to the project folder, and run:

```bat
cd frontend
npm install
npm run dev
```

`npm install` takes one to three minutes the first time only. Then open **<http://localhost:5173>** in your browser and log in.

### Starting it again another day

You do not repeat the setup. PostgreSQL starts with Windows. Then open two Command Prompt windows:

```bat
:: Window 1
cd backend
venv\Scripts\activate
python run.py

:: Window 2
cd frontend
npm run dev
```

---

## 4. Troubleshooting

**`python` is not recognized.** Python is not on PATH. Re-run the installer and tick *Add python.exe to PATH*, or use `py -3.12`.

**`pip install` fails with a long error about building a wheel.** You almost certainly have Python 3.13 or newer. Install Python 3.12 and recreate the environment (`rmdir /s /q venv`, then `python -m venv venv` again).

**`ModuleNotFoundError: No module named 'flask'` (or similar).** The virtual environment is not active. Run `venv\Scripts\activate` from the `backend` folder and make sure `(venv)` shows in your prompt.

**`password authentication failed for user "postgres"`.** The password in `DATABASE_URL` is wrong. Edit `backend\.env`. If the password has special characters, see the URL-encoding note in step 3.2.

**`database "electricity_forecasting" does not exist`.** Create it (step 2.4).

**`could not connect to server` / connection refused.** PostgreSQL is not running. Press Windows + R, type `services.msc`, find **postgresql-x64-16**, and start it. Also check the port in `DATABASE_URL` matches the one you chose at install (default 5432).

**The browser shows "Cannot reach the server".** The backend is not running. Start it (step 3.4) and keep that window open. The frontend only works while the backend is running.

**`Address already in use` on port 5000 or 5173.** Another program is using that port. Close the other copy of the app (check for an old Command Prompt window still running it).

**`npm install` shows warnings.** Warnings are normal. Only a final line starting with `npm ERR!` is a real problem. Check your internet connection and try again.

**The dashboard says there is no data, or "Train a model".** The database is empty or no model is trained. Run the seed (step 3.3), or in the app use *Data import* then *Model performance → Train model*.

**Training says "At least 28 days of hourly data are required".** Models need four weeks of hourly readings to learn weekly patterns. Import more history.

**I forgot my demo login.** See section 5.

**I want to start completely fresh.** In pgAdmin, right-click the `electricity_forecasting` database, delete it, create it again (step 2.4), and re-run `python seed_database.py`. Also delete the folder `backend\trained_models\household_1` (and any other `household_*` folders).

---

## 5. Demo accounts (development only)

`seed_database.py` creates these for local use. They are **not real people** and must never be used on a public server.

- **Household user:** `demo@example.com` / `ChangeMe123!`
- **Administrator:** `admin@example.com` / `ChangeMe123!`

On the login screen, the *Fill demo login* link types the household user in for you. Only the administrator can open the **Admin** page and change the tariff and anomaly thresholds. (The administrator account has no household of its own; use the demo user to see the dashboards.)

You can also register your own account on the *Create an account* page; you will be asked to set up a household first.

---

## 6. Try the full demonstration

Everything here is a real operation against the database and the trained models.

1. **Log in** as the demo user (or register a new account).
2. **Create a household** (only needed for a new account; the demo user already has one).
3. **Import data** on *Data import*: upload a CSV, or use *Load the demo dataset*. A CSV needs the columns `timestamp` and `consumption_kwh` (optional: `temperature`, `humidity`).
4. The import report shows how many rows were processed, valid, invalid, repaired and de-duplicated, with the exact rows that had problems.
5. Open **Model performance** and press **Train model** (the button says *Retrain model* if one already exists, as it does after seeding). Training takes 20 seconds to a couple of minutes.
6. The page shows the measured MAE, RMSE and MAPE for both models, the comparison charts, and which features the Random Forest relies on.
7. Open **Forecast**, pick 24 hours / 3 days / 7 days / 30 days and press **Generate forecast**.
8. You see expected consumption, the 90% prediction range, the estimated cost and the model used.
9. **Introduce an unusual reading.** On *Consumption* sort by newest to find the last reading, then on *Data import → Enter a reading* save a reading for **the very next hour** with a high value such as `4` kWh.
10. The system re-checks the data immediately and detects it.
11. It calculates the actual and expected consumption, the difference, the percentage deviation, the anomaly score and the severity.
12. The **Dashboard** shows a banner such as "Abnormal consumption detected: usage is X% above the expected pattern". The percentage is calculated from the stored values, never typed in.
13. An **alert** appears (the bell and the *Alerts* page).
14. Click **View anomaly** to open the detail panel with the plain-language reasons.
15. Use **Export report** on the *Anomalies* page to download the CSV, and **Summary PDF** on the *Dashboard* for a one-page report of the selected period.

---

## 7. Running the tests

Backend (from the `backend` folder, with `(venv)` active). The tests use an in-memory SQLite database, so they do **not** touch your PostgreSQL data:

```bat
python -m pytest -q
```

This takes about a minute because two tests train real models. For a faster run:

```bat
python -m pytest -q -m "not slow"
```

Frontend (from the `frontend` folder):

```bat
npm test
```

---

## 8. Generating demo data as a file

You can create synthetic CSV files to practise uploading:

```bat
cd backend
python generate_dataset.py --households 1 --days 120
```

`--households` can be `1`, `5` or `10`. The files are written to `backend\datasets\` along with an `*_anomaly_labels.csv` that lists exactly which anomalies were injected (useful for checking the detector). Upload a file through *Data import*.

---

## 9. How it works

### Architecture

```
        React UI  (Vite, Tailwind, Recharts)
              |
           REST API  (JSON, JWT)
              |
        Flask backend
   auth · ingestion · forecasting · anomaly detection · alerts
        |                         |
   PostgreSQL              trained models (joblib)
```

In development the Vite server forwards `/api` requests to Flask, so there are no browser cross-origin problems.

### The machine-learning pipeline

1. **Validate and clean.** Required columns are checked. Bad timestamps, non-numbers, negative or implausible values are rejected and reported. Duplicate timestamps are removed. Missing values are repaired by time interpolation (short gaps) or by the typical value for that hour of the day, never by blindly inserting zero. Times are stored in UTC and shown in **Africa/Nairobi**.
2. **Regularise.** Records are resampled to a regular hourly series (energy is summed within each hour).
3. **Features.** Calendar features (hour, day of week/month, month, week of year, weekend, Kenyan public holiday), lags (1, 2, 3, 24, 48, 168 hours), rolling means (3, 6, 24 hours) and a 24-hour rolling standard deviation, plus temperature and humidity when supplied. Rolling features are computed from the *previous* hours only, so a value never leaks into its own features.
4. **Two forecasting models,** compared fairly: a **Random Forest** on those features and a **SARIMA** time-series model. The data is split **in time order** (first 80% to train, last 20% to test; no shuffling). Both models are scored the same way: at each midnight of the test period, forecast the next 24 hours using only earlier data.
5. **Selection.** MAE, RMSE and MAPE are measured on the unseen 20%. The model with the better value of the configured metric (default MAE) is refitted on all the data and saved. The numbers shown in the app are the measured ones.
6. **Prediction ranges.** For the Random Forest, the 90% range comes from the model's real validation errors for each hour of the day. For SARIMA it comes from the model's own forecast variance. These are not fixed percentages.
7. **Expected consumption.** For every past hour, the expected value is predicted by a model that did **not** see that hour during training (the history is split into blocks and each block is predicted by a model trained on the others).
8. **Anomaly detection.** An hour is a candidate if an **Isolation Forest** flags it or its error is statistically extreme for that hour of day. It is reported only if the deviation is at least the *Low* threshold and at least 0.25 kWh in absolute terms.
9. **Severity.** From the percentage deviation: Normal below 10%, Low 10–20%, Medium 20–35%, High 35–50%, Critical above 50%. These are **system-defined, configurable defaults, not official Kenya Power thresholds**.
10. **Types.** Spike, sustained high usage, sudden drop, unusual-time usage, and a longer-term pattern change.
11. **Explanations** are generated from the data (compared with the household's average for that hour, the model's expected range, the previous hours, night-time, temperature). The app never claims that a particular appliance caused something, because it only sees whole-house totals.

Models are trained only when you press *Train model* (or an administrator retrains), never on each request. Trained files are saved under `backend\trained_models\household_<id>\` as `forecasting_model.joblib`, `anomaly_model.joblib` and `model_metadata.json`.

### Cost estimates

Costs are `kWh × the configured tariff`. No official Kenya Power tariff is built in; an administrator sets the name, price per kWh, currency and effective date. The seeded value (25 KES/kWh) is a **placeholder labelled as such**, and every cost in the app is labelled an *estimate*.

---

## 10. Database design

Tables are created automatically.

- `users`: name, email, password hash (never the password), role (`USER` or `ADMIN`).
- `households`: owner, name, location, size.
- `consumption_records`: household, timestamp, kWh, temperature, humidity, source (`csv`, `manual`, `demo`). One reading per household per timestamp.
- `forecasts`: forecast time, predicted kWh, lower and upper bound, model name.
- `anomalies`: the reading, expected and actual kWh, difference, percentage difference, score, severity, type, status, explanation.
- `model_runs`: model name, training records, MAE, RMSE, MAPE, training time, whether it is the active model, feature importance.
- `alerts`: user, anomaly, title, message, severity, read flag.
- `tariff_settings`: name, cost per kWh, currency, effective date.
- `system_settings`: key/value settings (anomaly thresholds, model-selection metric).

Indexes cover timestamp, household, severity and creation time.

---

## 11. API overview

All routes are under `/api`, return JSON in the form `{ "success": true, "data": … }` (or `{ "success": false, "error": { "message": … } }`), and need a `Bearer` token except register and login.

- **Auth:** `POST /auth/register`, `POST /auth/login`, `GET /auth/me`
- **Household:** `GET /household`, `POST /household`, `PUT /household`
- **Consumption:** `GET /consumption` (search, date and kWh filters, sorting, pagination), `POST /consumption` (manual reading), `POST /consumption/upload` (CSV), `POST /consumption/demo`, `DELETE /consumption/<id>`, `GET /consumption/export`
- **Machine learning:** `POST /ml/train`, `GET /ml/models`, `GET /ml/performance`
- **Forecast:** `POST /forecast/generate`, `GET /forecast`, `GET /forecast/export`
- **Anomalies:** `GET /anomalies`, `GET /anomalies/summary`, `GET /anomalies/<id>`, `PATCH /anomalies/<id>` (review status), `POST /anomalies/detect`, `GET /anomalies/export`
- **Alerts:** `GET /alerts`, `PATCH /alerts/<id>/read`, `POST /alerts/read-all`
- **Dashboard:** `GET /dashboard/summary`, `GET /dashboard/chart`, `GET /dashboard/recommendations`
- **Settings:** `GET`/`PUT /settings/tariff`, `/settings/thresholds`, `/settings/model` (changes are admin-only)
- **Admin (admin only):** `GET /admin/stats`, `/admin/users`, `/admin/households`, `/admin/models`, `PATCH`/`DELETE /admin/users/<id>`, `POST /admin/retrain/<household_id>`
- **Reports:** `GET /reports/summary.pdf`

Errors use proper status codes (400, 401, 403, 404, 409, 422, 500) and never expose stack traces. A user can only reach their own household's data.

---

## 12. Project layout

```
electricity-forecasting-system/
├── backend/
│   ├── app/
│   │   ├── models/      database tables (SQLAlchemy)
│   │   ├── routes/      REST endpoints
│   │   ├── services/    ingestion, training, anomaly persistence, settings
│   │   ├── ml/          preprocessing, features, forecasting, anomaly detection, synthetic data
│   │   ├── schemas/     input validation
│   │   └── utils/       responses, auth, time zone, Kenyan holidays
│   ├── tests/           pytest suite
│   ├── trained_models/  saved models (created when you train)
│   ├── datasets/        generated CSV files
│   ├── seed_database.py
│   ├── generate_dataset.py
│   ├── run.py
│   └── requirements.txt
├── frontend/
│   └── src/             pages, components, layouts, context, services, hooks, utils
├── docs/screenshots/
└── README.md
```

---

## 13. Screenshots

Taken from the running application with the synthetic demo dataset.

![Dashboard](docs/screenshots/dashboard.png)

![Anomalies](docs/screenshots/anomalies.png)

![Anomaly details](docs/screenshots/anomaly-details.png)

![Forecast](docs/screenshots/forecast.png)

![Model performance](docs/screenshots/model-performance.png)

![Light theme](docs/screenshots/dashboard-light.png)

![Mobile](docs/screenshots/mobile.png)

---

## 14. Limitations

Please keep these in any report or presentation. They are real.

- **Synthetic data is not real data.** The demo data is simulated and is not equivalent to real Kenya Power or household meter data. Results on real data will differ. The injected anomalies are also fairly obvious, so detection results on them are optimistic.
- **Detection is imperfect.** On the synthetic data the detector finds most strong anomalies but misses most mild ones, and flags some normal hours. Measure it again on any real data you use.
- **One anomaly can disturb the next day's expectations.** Expected values are built from recent hours, so a large anomaly late in the evening can inflate the expected usage the next morning, which then shows up as a run of "sudden drop" flags even though the readings are normal (visible around 6 April in the anomalies screenshot). Cleaning flagged hours out of the history before predicting would reduce this; it is not implemented yet.
- **Severity saturates on small readings.** Percentage thresholds on hourly values of a few tenths of a kWh push most detected anomalies to *Critical*. The thresholds can be changed by an administrator.
- **No appliance-level information.** Only whole-house totals are available, so the system cannot say which appliance caused anything.
- **Anomalies are not proof of faults.** A flagged hour is an unusual pattern. It does not prove equipment failure, meter tampering or electricity theft.
- **Weather is optional.** If temperature and humidity are not supplied they are simply not used. For future hours the forecast assumes typical weather for that hour of the day, because no weather forecast is connected.
- **Accuracy depends on data.** At least 28 days of hourly data are required, and more is better. Forecast ranges are calibrated on 24-hour-ahead errors, so for 7-day and 30-day forecasts the true uncertainty is larger than the range shown.
- **SARIMA** is fitted on the most recent 60 days with a daily cycle only; it does not model weekly patterns.
- **Holidays.** Fixed Kenyan public holidays, Good Friday and Easter Monday are included. Eid dates and one-off declared holidays are not.
- **Data frequency.** The pipeline needs hourly or finer readings. Daily-only data is rejected for forecasting.
- **Costs are estimates** based on the tariff an administrator configures.
- **Training runs inside the request** and can take up to a few minutes on a slow laptop; the page shows a progress state until it finishes.
- **Development setup.** It uses Flask's development server on one machine. It has been exercised on Linux with PostgreSQL 16 and Chromium; the Windows steps above follow the standard installers but were not run on a Windows machine. Email and SMS alerts are not included (alerts are in-app only).

---

## 15. Project status and future improvements

**Included:** backend, database, machine-learning pipeline, React frontend, tests (backend and frontend), seeding, synthetic data generator.

**Still to be added:** the `notebooks/` (data exploration, model training, anomaly analysis), the `docs/` report material (problem statement, objectives, scope, requirements, architecture, database design, ML methodology, testing strategy, limitations, future work), and a formal OpenAPI/Swagger document.

**Ideas for later:** smart-meter API integration, IoT sensors, real-time streaming, appliance-level monitoring, a weather API, a tariff API, SMS and email alerts, a mobile app, deep-learning models such as LSTM or GRU, solar generation prediction, and household energy-saving recommendations.
