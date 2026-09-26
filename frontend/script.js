const API_BASE = "http://127.0.0.1:8000";

const authScreen = document.getElementById("authScreen");
const dashboard = document.getElementById("dashboard");
const loginTab = document.getElementById("loginTab");
const registerTab = document.getElementById("registerTab");
const loginForm = document.getElementById("loginForm");
const registerForm = document.getElementById("registerForm");
const authMessage = document.getElementById("authMessage");
const userEmail = document.getElementById("userEmail");
const logoutBtn = document.getElementById("logoutBtn");

let accessToken = sessionStorage.getItem("weather_access_token");
let map = null;
let mapInitialized = false;
const markers = {};

function setAuthMessage(message = "", type = "") {
    authMessage.textContent = message;
    authMessage.className = `auth-message ${type}`;
}

function showAuthScreen(message = "") {
    accessToken = null;
    sessionStorage.removeItem("weather_access_token");
    dashboard.hidden = true;
    authScreen.hidden = false;
    setAuthMessage(message, message ? "error" : "");
}

function showDashboard(user) {
    authScreen.hidden = true;
    dashboard.hidden = false;
    userEmail.textContent = user.email;
    initializeMap();
    window.setTimeout(() => map.invalidateSize(), 0);
    checkApi();
    loadForecast("Delhi");
}

async function apiFetch(path, options = {}) {
    const headers = new Headers(options.headers || {});
    if (accessToken) {
        headers.set("Authorization", `Bearer ${accessToken}`);
    }
    const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
    if (response.status === 401 && path !== "/auth/login") {
        showAuthScreen("Your session has ended. Please log in again.");
    }
    return response;
}

function switchAuthForm(mode) {
    const showLogin = mode === "login";
    loginForm.hidden = !showLogin;
    registerForm.hidden = showLogin;
    loginTab.classList.toggle("active", showLogin);
    registerTab.classList.toggle("active", !showLogin);
    setAuthMessage();
}

async function submitAuth(event, endpoint, form) {
    event.preventDefault();
    const submitButton = form.querySelector("button[type='submit']");
    const originalText = submitButton.textContent;
    const email = form.querySelector("input[type='email']").value;
    const password = form.querySelector("input[type='password']").value;
    submitButton.disabled = true;
    submitButton.textContent = "Please wait...";
    setAuthMessage();

    try {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password })
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || "Authentication request failed.");
        }
        accessToken = data.access_token;
        sessionStorage.setItem("weather_access_token", accessToken);
        form.reset();
        showDashboard(data.user);
    } catch (error) {
        setAuthMessage(error.message, "error");
    } finally {
        submitButton.disabled = false;
        submitButton.textContent = originalText;
    }
}

loginTab.addEventListener("click", () => switchAuthForm("login"));
registerTab.addEventListener("click", () => switchAuthForm("register"));
loginForm.addEventListener("submit", event => submitAuth(event, "/auth/login", loginForm));
registerForm.addEventListener("submit", event => submitAuth(event, "/auth/register", registerForm));
logoutBtn.addEventListener("click", () => showAuthScreen());


/* ============================================================
   CITY COORDINATES
============================================================ */

const CITY_COORDS = {

    Delhi: [
        28.6139,
        77.2090
    ],

    Mumbai: [
        19.0760,
        72.8777
    ],

    Bengaluru: [
        12.9716,
        77.5946
    ],

    Chennai: [
        13.0827,
        80.2707
    ],

    Bhopal: [
        23.2599,
        77.4126
    ]

};


/* ============================================================
   DOM ELEMENTS
============================================================ */

const citySelect =
    document.getElementById("citySelect");

const searchBtn =
    document.getElementById("searchBtn");

const apiStatus =
    document.getElementById("apiStatus");

const selectedCity =
    document.getElementById("selectedCity");

const currentTemp =
    document.getElementById("currentTemp");

const nextHour =
    document.getElementById("nextHour");

const nextHourTime =
    document.getElementById("nextHourTime");

const forecastDays =
    document.getElementById("forecastDays");

const forecastGrid =
    document.getElementById("forecastGrid");

const forecastStatus =
    document.getElementById("forecastStatus");

const hourlyStatus =
    document.getElementById("hourlyStatus");

const mapLocation =
    document.getElementById("mapLocation");


/* ============================================================
   MAP
============================================================ */

function initializeMap() {

    if (mapInitialized) {
        return;
    }

    map = L.map("map", {

    worldCopyJump: true,

    minZoom: 2,

    maxZoom: 12

    }).setView(

    [22.5, 78.9],

    4

    );


    L.tileLayer(

    "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",

    {

        maxZoom: 19,

        attribution:
            "&copy; OpenStreetMap contributors"

    }

    ).addTo(map);


    Object.entries(CITY_COORDS).forEach(

    ([city, coords]) => {

        const marker = L.marker(
            coords
        )
        .addTo(map)
        .bindPopup(

            `<strong>${city}</strong>
             <br>
             Click Forecast to view AI predictions.`

        );


        marker.on(
            "click",
            () => {

                citySelect.value = city;

                loadForecast(city);

            }
        );


        markers[city] = marker;

    }

    );

    mapInitialized = true;
}


/* ============================================================
   24-HOUR CHART
============================================================ */

let hourlyChart = null;


function createHourlyChart(predictions) {

    const canvas =
        document.getElementById("hourlyChart");


    const labels = predictions.map(
        item => {

            const date =
                new Date(item.time);

            return date.toLocaleTimeString(
                "en-IN",
                {
                    hour: "2-digit",
                    minute: "2-digit"
                }
            );

        }
    );


    const temperatures =
        predictions.map(
            item =>
                item.predicted_temperature
        );


    if (hourlyChart !== null) {

        hourlyChart.destroy();

    }


    hourlyChart = new Chart(

        canvas,

        {

            type: "line",

            data: {

                labels: labels,

                datasets: [

                    {

                        label:
                            "Predicted Temperature (°C)",

                        data:
                            temperatures,

                        borderWidth: 3,

                        tension: 0.35,

                        fill: true,

                        pointRadius: 4,

                        pointHoverRadius: 7

                    }

                ]

            },


            options: {

                responsive: true,

                maintainAspectRatio: false,


                interaction: {

                    intersect: false,

                    mode: "index"

                },


                plugins: {

                    legend: {

                        display: true

                    },


                    tooltip: {

                        callbacks: {

                            label: function(context) {

                                return (
                                    " Temperature: " +
                                    context.parsed.y +
                                    " °C"
                                );

                            }

                        }

                    }

                },


                scales: {

                    x: {

                        title: {

                            display: true,

                            text:
                                "Time"

                        },

                        ticks: {

                            maxTicksLimit: 12

                        }

                    },


                    y: {

                        title: {

                            display: true,

                            text:
                                "Temperature (°C)"

                        }

                    }

                }

            }

        }

    );

}


/* ============================================================
   API STATUS
============================================================ */

function setApiStatus(
    online,
    text
) {

    apiStatus.innerHTML = `

        <span
            class="status-dot">
        </span>

        ${text}

    `;


    apiStatus
        .querySelector(".status-dot")
        .style.background =
            online
                ? "#35d07f"
                : "#ff6262";

}


/* ============================================================
   CHECK FASTAPI
============================================================ */

async function checkApi() {

    try {

        const response =
            await fetch(
                `${API_BASE}/health`
            );


        if (!response.ok) {

            throw new Error(
                "API unavailable"
            );

        }


        const data =
            await response.json();


        setApiStatus(
            true,
            "API Online"
        );


        return data;

    }

    catch (error) {

        setApiStatus(
            false,
            "API Offline"
        );


        console.error(error);

    }

}


/* ============================================================
   FORMAT DATE
============================================================ */

function formatDate(
    dateString
) {

    return new Date(
        dateString + "T00:00:00"
    ).toLocaleDateString(

        "en-IN",

        {

            weekday: "short",

            day: "numeric",

            month: "short"

        }

    );

}


/* ============================================================
   LOAD FORECAST
============================================================ */

async function loadForecast(
    city
) {

    searchBtn.disabled =
        true;


    searchBtn.textContent =
        "Loading...";


    forecastStatus.textContent =
        "Generating forecast...";


    hourlyStatus.textContent =
        "Generating 24-hour forecast...";


    forecastGrid.innerHTML = `

        <div class="forecast-item">

            Loading AI forecast...

        </div>

    `;


    selectedCity.textContent =
        city;


    mapLocation.textContent =
        city;


    const coords =
        CITY_COORDS[city];


    if (coords) {

        map.flyTo(

            coords,

            6,

            {
                duration: 1.2
            }

        );


        if (markers[city]) {

            markers[city].openPopup();

        }

    }


    try {

        /*
         * Three real FastAPI endpoints:
         *
         * /predict/{city}
         * /predict/tomorrow/{city}
         * /predict/10days/{city}
         */

        const [

            nextHourResponse,

            hourlyResponse,

            forecastResponse

        ] = await Promise.all([

            apiFetch(
                `/predict/${encodeURIComponent(city)}`
            ),

            apiFetch(
                `/predict/tomorrow/${encodeURIComponent(city)}`
            ),

            apiFetch(
                `/predict/10days/${encodeURIComponent(city)}`
            )

        ]);


        if (!nextHourResponse.ok) {

            throw new Error(
                `Next-hour API error: ${nextHourResponse.status}`
            );

        }


        if (!hourlyResponse.ok) {

            throw new Error(
                `24-hour API error: ${hourlyResponse.status}`
            );

        }


        if (!forecastResponse.ok) {

            throw new Error(
                `10-day API error: ${forecastResponse.status}`
            );

        }


        const nextHourData =
            await nextHourResponse.json();


        const hourlyData =
            await hourlyResponse.json();


        const forecastData =
            await forecastResponse.json();


        /* ====================================================
           CURRENT / NEXT HOUR
        ==================================================== */

        currentTemp.textContent =
            nextHourData.latest_temperature;


        nextHour.textContent =
            `${nextHourData.predicted_temperature} °C`;


        nextHourTime.textContent =
            `For ${
                new Date(
                    nextHourData.prediction_time
                ).toLocaleString("en-IN")
            }`;


        /* ====================================================
           24 HOUR GRAPH
        ==================================================== */

        createHourlyChart(
            hourlyData.predictions
        );


        hourlyStatus.textContent =
            `${hourlyData.forecast_hours} hourly predictions`;


        /* ====================================================
           10 DAY FORECAST
        ==================================================== */

        forecastDays.textContent =
            `${forecastData.forecast_days} days`;


        renderForecast(
            forecastData.daily_forecast
        );


        forecastStatus.textContent =
            `${forecastData.forecast_hours} hourly predictions`;


        setApiStatus(
            true,
            "API Online"
        );

    }


    catch (error) {

        console.error(error);


        forecastGrid.innerHTML = `

            <div class="forecast-item">

                <strong>
                    Unable to load forecast
                </strong>

                <p
                    style="
                    color:#9fb1c5;
                    margin-top:8px;
                    "
                >

                    Make sure FastAPI is running
                    on port 8000.

                </p>

            </div>

        `;


        hourlyStatus.textContent =
            "24-hour forecast unavailable";


        forecastStatus.textContent =
            "Forecast unavailable";

    }


    finally {

        searchBtn.disabled =
            false;


        searchBtn.textContent =
            "Forecast";

    }

}


/* ============================================================
   RENDER 10-DAY FORECAST
============================================================ */

function renderForecast(
    days
) {

    forecastGrid.innerHTML =
        "";


    days.forEach(
        day => {

            const card =
                document.createElement(
                    "div"
                );


            card.className =
                "forecast-item";


            card.innerHTML = `

                <div class="day">

                    Day ${day.day}

                </div>


                <div class="date">

                    ${formatDate(day.date)}

                </div>


                <div class="forecast-temp">

                    ${day.max_temperature}°C

                    <span>
                        /
                        ${day.min_temperature}°C
                    </span>

                </div>


                <div class="avg">

                    Average
                    ${day.avg_temperature}°C

                </div>

            `;


            forecastGrid.appendChild(
                card
            );

        }
    );

}


/* ============================================================
   SEARCH BUTTON
============================================================ */

searchBtn.addEventListener(

    "click",

    () => {

        loadForecast(
            citySelect.value
        );

    }

);


/* ============================================================
   CITY SELECT
============================================================ */

citySelect.addEventListener(

    "change",

    () => {

        const city =
            citySelect.value;


        const coords =
            CITY_COORDS[city];


        if (coords) {

            map.flyTo(

                coords,

                6,

                {
                    duration: 1.0
                }

            );


            markers[city].openPopup();

        }

    }

);


/* ============================================================
   INITIAL LOAD
============================================================ */

async function initializeApp() {
    if (!accessToken) {
        showAuthScreen();
        return;
    }

    try {
        const response = await apiFetch("/auth/me");
        if (!response.ok) {
            return;
        }
        showDashboard(await response.json());
    } catch (error) {
        showAuthScreen("Unable to restore your session. Please log in again.");
    }
}

initializeApp();
