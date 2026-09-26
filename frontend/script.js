const API_BASE = "http://127.0.0.1:8000";


/* ============================================================
   AUTHENTICATION ELEMENTS
============================================================ */

const authScreen =
    document.getElementById("authScreen");

const dashboard =
    document.getElementById("dashboard");

const loginTab =
    document.getElementById("loginTab");

const registerTab =
    document.getElementById("registerTab");

const loginForm =
    document.getElementById("loginForm");

const registerForm =
    document.getElementById("registerForm");

const authMessage =
    document.getElementById("authMessage");

const userEmail =
    document.getElementById("userEmail");

const logoutBtn =
    document.getElementById("logoutBtn");


/* ============================================================
   AUTH STATE
============================================================ */

let accessToken =
    localStorage.getItem("weather_access_token");

let currentUser =
    null;


/* ============================================================
   MAP STATE
============================================================ */

let map =
    null;

let mapInitialized =
    false;

const markers =
    {};


/* ============================================================
   CITY COORDINATES
   28 STATES + 8 UNION TERRITORIES
============================================================ */

const CITY_COORDS = {

    "Amaravati": [
        16.5745,
        80.3598
    ],

    "Itanagar": [
        27.0844,
        93.6053
    ],

    "Dispur": [
        26.1433,
        91.7898
    ],

    "Patna": [
        25.5941,
        85.1376
    ],

    "Raipur": [
        21.2514,
        81.6296
    ],

    "Panaji": [
        15.4909,
        73.8278
    ],

    "Gandhinagar": [
        23.2156,
        72.6369
    ],

    "Chandigarh": [
        30.7333,
        76.7794
    ],

    "Shimla": [
        31.1048,
        77.1734
    ],

    "Ranchi": [
        23.3441,
        85.3096
    ],

    "Bengaluru": [
        12.9716,
        77.5946
    ],

    "Thiruvananthapuram": [
        8.5241,
        76.9366
    ],

    "Bhopal": [
        23.2599,
        77.4126
    ],

    "Mumbai": [
        19.0760,
        72.8777
    ],

    "Imphal": [
        24.8170,
        93.9368
    ],

    "Shillong": [
        25.5788,
        91.8933
    ],

    "Aizawl": [
        23.7271,
        92.7176
    ],

    "Kohima": [
        25.6751,
        94.1086
    ],

    "Bhubaneswar": [
        20.2961,
        85.8245
    ],

    "Jaipur": [
        26.9124,
        75.7873
    ],

    "Gangtok": [
        27.3389,
        88.6065
    ],

    "Chennai": [
        13.0827,
        80.2707
    ],

    "Hyderabad": [
        17.3850,
        78.4867
    ],

    "Agartala": [
        23.8315,
        91.2868
    ],

    "Lucknow": [
        26.8467,
        80.9462
    ],

    "Dehradun": [
        30.3165,
        78.0322
    ],

    "Kolkata": [
        22.5726,
        88.3639
    ],

    "Port Blair": [
        11.6234,
        92.7265
    ],

    "Daman": [
        20.3974,
        72.8328
    ],

    "New Delhi": [
        28.6139,
        77.2090
    ],

    "Srinagar": [
        34.0837,
        74.7973
    ],

    "Jammu": [
        32.7266,
        74.8570
    ],

    "Leh": [
        34.1526,
        77.5771
    ],

    "Kavaratti": [
        10.5669,
        72.6420
    ],

    "Puducherry": [
        11.9416,
        79.8083
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
   AUTH MESSAGE
============================================================ */

function setAuthMessage(
    message = "",
    type = ""
) {

    authMessage.textContent =
        message;

    authMessage.className =
        `auth-message ${type}`;
}


/* ============================================================
   SHOW LOGIN SCREEN
============================================================ */

function showAuthScreen(
    message = ""
) {

    accessToken =
        null;

    currentUser =
        null;

    localStorage.removeItem(
        "weather_access_token"
    );

    dashboard.hidden =
        true;

    authScreen.hidden =
        false;

    setAuthMessage(
        message,
        message ? "error" : ""
    );
}


/* ============================================================
   SHOW DASHBOARD
============================================================ */

async function showDashboard(
    user
) {

    currentUser =
        user;

    authScreen.hidden =
        true;

    dashboard.hidden =
        false;

    userEmail.textContent =
        user.email;

    initializeMap();

    window.setTimeout(
        () => {

            if (map) {
                map.invalidateSize();
            }

        },
        100
    );

    await checkApi();

    await loadCities();

    await loadForecast(
        "Delhi"
    );
}


/* ============================================================
   GENERIC API FETCH
============================================================ */

async function apiFetch(
    path,
    options = {}
) {

    const headers =
        new Headers(
            options.headers || {}
        );


    if (accessToken) {

        headers.set(
            "Authorization",
            `Bearer ${accessToken}`
        );

    }


    const response =
        await fetch(
            `${API_BASE}${path}`,
            {
                ...options,
                headers
            }
        );


    /*
     * Token expired / invalid.
     */

    if (
        response.status === 401 &&
        !path.startsWith("/auth/login") &&
        !path.startsWith("/auth/register")
    ) {

        showAuthScreen(
            "Your session has ended. Please log in again."
        );

    }


    return response;
}


/* ============================================================
   SWITCH LOGIN / REGISTER
============================================================ */

function switchAuthForm(
    mode
) {

    const showLogin =
        mode === "login";


    loginForm.hidden =
        !showLogin;

    registerForm.hidden =
        showLogin;


    loginTab.classList.toggle(
        "active",
        showLogin
    );

    registerTab.classList.toggle(
        "active",
        !showLogin
    );


    setAuthMessage();
}


/* ============================================================
   LOGIN / REGISTER
============================================================ */

async function submitAuth(
    event,
    endpoint,
    form
) {

    event.preventDefault();


    const submitButton =
        form.querySelector(
            "button[type='submit']"
        );


    const originalText =
        submitButton.textContent;


    const email =
        form.querySelector(
            "input[type='email']"
        ).value.trim();


    const password =
        form.querySelector(
            "input[type='password']"
        ).value;


    submitButton.disabled =
        true;

    submitButton.textContent =
        "Please wait...";


    setAuthMessage();


    try {

        const response =
            await fetch(
                `${API_BASE}${endpoint}`,
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({
                        email: email,
                        password: password
                    })
                }
            );


        let data = {};

        try {

            data =
                await response.json();

        } catch {

            data = {};

        }


        if (!response.ok) {

            throw new Error(
                data.detail ||
                "Authentication request failed."
            );

        }


        /*
         * Save JWT permanently in browser storage.
         */

        accessToken =
            data.access_token;


        localStorage.setItem(
            "weather_access_token",
            accessToken
        );


        form.reset();


        await showDashboard(
            data.user
        );

    }


    catch (error) {

        console.error(
            "Authentication error:",
            error
        );


        setAuthMessage(
            error.message ||
            "Authentication failed.",
            "error"
        );

    }


    finally {

        submitButton.disabled =
            false;

        submitButton.textContent =
            originalText;

    }

}


/* ============================================================
   AUTH EVENTS
============================================================ */

loginTab.addEventListener(
    "click",
    () => switchAuthForm("login")
);


registerTab.addEventListener(
    "click",
    () => switchAuthForm("register")
);


loginForm.addEventListener(
    "submit",
    event =>
        submitAuth(
            event,
            "/auth/login",
            loginForm
        )
);


registerForm.addEventListener(
    "submit",
    event =>
        submitAuth(
            event,
            "/auth/register",
            registerForm
        )
);


logoutBtn.addEventListener(
    "click",
    () => {

        showAuthScreen();

        switchAuthForm(
            "login"
        );

    }
);


/* ============================================================
   LOAD CITIES FROM FASTAPI
============================================================ */

async function loadCities() {

    try {

        const response =
            await apiFetch(
                "/cities"
            );


        if (!response.ok) {

            throw new Error(
                `Unable to load cities: ${response.status}`
            );

        }


        const data =
            await response.json();


        /*
         * Support either:
         *
         * ["Delhi", "Mumbai", ...]
         *
         * OR:
         *
         * {"cities": ["Delhi", "Mumbai", ...]}
         */

        let cities;


        if (Array.isArray(data)) {

            cities =
                data;

        }

        else if (
            data &&
            Array.isArray(data.cities)
        ) {

            cities =
                data.cities;

        }

        else {

            throw new Error(
                "Invalid /cities response format."
            );

        }


        /*
         * Remove duplicates and sort alphabetically.
         */

        cities =
            [...new Set(cities)]
                .sort(
                    (a, b) =>
                        a.localeCompare(b)
                );


        citySelect.innerHTML =
            "";


        cities.forEach(
            city => {

                const option =
                    document.createElement(
                        "option"
                    );

                option.value =
                    city;

                option.textContent =
                    city;

                citySelect.appendChild(
                    option
                );

            }
        );


        /*
         * Prefer Delhi as initial city.
         */

        if (
            cities.includes("Delhi")
        ) {

            citySelect.value =
                "Delhi";

        }

        else if (cities.length > 0) {

            citySelect.value =
                cities[0];

        }


        /*
         * Rebuild map markers using
         * only cities supported by backend.
         */

        addCityMarkers(
            cities
        );


        console.log(
            `Loaded ${cities.length} cities from FastAPI.`
        );

    }


    catch (error) {

        console.error(
            "City loading error:",
            error
        );


        /*
         * Fallback to known coordinates
         * if /cities temporarily fails.
         */

        const fallbackCities =
            Object.keys(
                CITY_COORDS
            );


        citySelect.innerHTML =
            "";


        fallbackCities
            .sort(
                (a, b) =>
                    a.localeCompare(b)
            )
            .forEach(
                city => {

                    const option =
                        document.createElement(
                            "option"
                        );

                    option.value =
                        city;

                    option.textContent =
                        city;

                    citySelect.appendChild(
                        option
                    );

                }
            );


        citySelect.value =
            "Delhi";


        addCityMarkers(
            fallbackCities
        );

    }

}


/* ============================================================
   MAP
============================================================ */

function initializeMap() {

    if (mapInitialized) {

        return;

    }


    map =
        L.map(
            "map",
            {

                worldCopyJump: true,

                minZoom: 2,

                maxZoom: 12

            }
        ).setView(

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

    ).addTo(
        map
    );


    mapInitialized =
        true;

}


/* ============================================================
   ADD CITY MARKERS
============================================================ */

function addCityMarkers(
    cities
) {

    if (!map) {

        return;

    }


    cities.forEach(
        city => {

            const coords =
                CITY_COORDS[city];


            if (!coords) {

                console.warn(
                    `No coordinates found for ${city}`
                );

                return;

            }


            /*
             * Don't create duplicate marker.
             */

            if (markers[city]) {

                return;

            }


            const marker =
                L.marker(
                    coords
                )
                .addTo(map)
                .bindPopup(

                    `
                    <strong>${city}</strong>
                    <br>
                    Click Forecast to view AI predictions.
                    `

                );


            marker.on(
                "click",
                () => {

                    citySelect.value =
                        city;

                    loadForecast(
                        city
                    );

                }
            );


            markers[city] =
                marker;

        }
    );

}


/* ============================================================
   24-HOUR CHART
============================================================ */

let hourlyChart =
    null;


function createHourlyChart(
    predictions
) {

    const canvas =
        document.getElementById(
            "hourlyChart"
        );


    if (
        !predictions ||
        predictions.length === 0
    ) {

        hourlyStatus.textContent =
            "No hourly predictions available.";

        return;

    }


    const labels =
        predictions.map(
            item => {

                const date =
                    new Date(
                        item.time
                    );


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
                Number(
                    item.predicted_temperature
                )
        );


    if (
        hourlyChart !== null
    ) {

        hourlyChart.destroy();

    }


    hourlyChart =
        new Chart(

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

                                label:
                                    function(context) {

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

                                maxTicksLimit:
                                    12

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

        <span class="status-dot"></span>

        ${text}

    `;


    const dot =
        apiStatus.querySelector(
            ".status-dot"
        );


    if (dot) {

        dot.style.background =
            online
                ? "#35d07f"
                : "#ff6262";

    }

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


        console.error(
            "FastAPI health check:",
            error
        );


        return null;

    }

}


/* ============================================================
   FORMAT DATE
============================================================ */

function formatDate(
    dateString
) {

    if (!dateString) {

        return "--";

    }


    /*
     * Handles:
     *
     * 2026-09-27
     * 2026-09-27T00:00:00
     */

    const normalized =
        String(
            dateString
        ).includes("T")
            ? String(dateString)
            : `${dateString}T00:00:00`;


    const date =
        new Date(
            normalized
        );


    if (
        Number.isNaN(
            date.getTime()
        )
    ) {

        return dateString;

    }


    return date.toLocaleDateString(
        "en-IN",
        {

            weekday:
                "short",

            day:
                "numeric",

            month:
                "short"

        }
    );

}


/* ============================================================
   LOAD FORECAST
============================================================ */

async function loadForecast(
    city
) {

    if (!city) {

        return;

    }


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


    /*
     * Keep dropdown synchronized.
     */

    citySelect.value =
        city;


    /*
     * Move map to selected city.
     */

    const coords =
        CITY_COORDS[city];


    if (
        coords &&
        map
    ) {

        map.flyTo(

            coords,

            6,

            {
                duration:
                    1.2
            }

        );


        if (
            markers[city]
        ) {

            markers[city].openPopup();

        }

    }


    try {

        /*
         * Three FastAPI endpoints:
         *
         * 1. XGBoost
         *    /predict/{city}
         *
         * 2. GRU 24-hour
         *    /predict/tomorrow/{city}
         *
         * 3. GRU 10-day
         *    /predict/10days/{city}
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


        /*
         * If token expired, apiFetch()
         * already moved the user to login.
         */

        if (
            nextHourResponse.status === 401 ||
            hourlyResponse.status === 401 ||
            forecastResponse.status === 401
        ) {

            return;

        }


        if (!nextHourResponse.ok) {

            const errorData =
                await safeJson(
                    nextHourResponse
                );

            throw new Error(
                errorData.detail ||
                `Next-hour API error: ${nextHourResponse.status}`
            );

        }


        if (!hourlyResponse.ok) {

            const errorData =
                await safeJson(
                    hourlyResponse
                );

            throw new Error(
                errorData.detail ||
                `24-hour API error: ${hourlyResponse.status}`
            );

        }


        if (!forecastResponse.ok) {

            const errorData =
                await safeJson(
                    forecastResponse
                );

            throw new Error(
                errorData.detail ||
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
           CURRENT TEMPERATURE
        ==================================================== */

        currentTemp.textContent =
            formatTemperature(
                nextHourData.latest_temperature
            );


        /* ====================================================
           NEXT HOUR
        ==================================================== */

        nextHour.textContent =
            `${formatTemperature(
                nextHourData.predicted_temperature
            )} °C`;


        nextHourTime.textContent =
            `For ${
                formatDateTime(
                    nextHourData.prediction_time
                )
            }`;


        /* ====================================================
           24-HOUR GRAPH
        ==================================================== */

        createHourlyChart(
            hourlyData.predictions || []
        );


        hourlyStatus.textContent =
            `${hourlyData.forecast_hours || 0} hourly predictions`;


        /* ====================================================
           10-DAY FORECAST
        ==================================================== */

        forecastDays.textContent =
            `${forecastData.forecast_days || 0} days`;


        renderForecast(
            forecastData.daily_forecast || []
        );


        forecastStatus.textContent =
            `${forecastData.forecast_hours || 0} hourly predictions`;


        setApiStatus(
            true,
            "API Online"
        );

    }


    catch (error) {

        console.error(
            `Forecast error for ${city}:`,
            error
        );


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

                    ${escapeHtml(
                        error.message ||
                        "An unexpected error occurred."
                    )}

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
   SAFE JSON RESPONSE
============================================================ */

async function safeJson(
    response
) {

    try {

        return await response.json();

    }

    catch {

        return {};

    }

}


/* ============================================================
   FORMAT TEMPERATURE
============================================================ */

function formatTemperature(
    value
) {

    if (
        value === null ||
        value === undefined ||
        value === ""
    ) {

        return "--";

    }


    const number =
        Number(value);


    if (
        Number.isNaN(number)
    ) {

        return value;

    }


    return number.toFixed(2);

}


/* ============================================================
   FORMAT DATE + TIME
============================================================ */

function formatDateTime(
    dateString
) {

    if (!dateString) {

        return "--";

    }


    const date =
        new Date(
            dateString
        );


    if (
        Number.isNaN(
            date.getTime()
        )
    ) {

        return dateString;

    }


    return date.toLocaleString(
        "en-IN",
        {

            day:
                "numeric",

            month:
                "short",

            hour:
                "2-digit",

            minute:
                "2-digit"

        }
    );

}


/* ============================================================
   ESCAPE HTML
============================================================ */

function escapeHtml(
    value
) {

    return String(value)
        .replace(
            /&/g,
            "&amp;"
        )
        .replace(
            /</g,
            "&lt;"
        )
        .replace(
            />/g,
            "&gt;"
        )
        .replace(
            /"/g,
            "&quot;"
        )
        .replace(
            /'/g,
            "&#039;"
        );

}


/* ============================================================
   RENDER 10-DAY FORECAST
============================================================ */

function renderForecast(
    days
) {

    forecastGrid.innerHTML =
        "";


    if (
        !days ||
        days.length === 0
    ) {

        forecastGrid.innerHTML = `

            <div class="forecast-item">

                No forecast data available.

            </div>

        `;

        return;

    }


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

                    Day ${escapeHtml(
                        day.day
                    )}

                </div>


                <div class="date">

                    ${escapeHtml(
                        formatDate(
                            day.date
                        )
                    )}

                </div>


                <div class="forecast-temp">

                    ${formatTemperature(
                        day.max_temperature
                    )}°C

                    <span>
                        /
                        ${formatTemperature(
                            day.min_temperature
                        )}°C
                    </span>

                </div>


                <div class="avg">

                    Average
                    ${formatTemperature(
                        day.avg_temperature
                    )}°C

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


        if (
            coords &&
            map
        ) {

            map.flyTo(

                coords,

                6,

                {
                    duration:
                        1.0
                }

            );


            if (
                markers[city]
            ) {

                markers[city].openPopup();

            }

        }

    }
);


/* ============================================================
   INITIALIZE APPLICATION
============================================================ */

async function initializeApp() {

    /*
     * No saved JWT.
     * Show login screen.
     */

    if (!accessToken) {

        showAuthScreen();

        return;

    }


    try {

        /*
         * Verify saved JWT.
         */

        const response =
            await apiFetch(
                "/auth/me"
            );


        if (!response.ok) {

            showAuthScreen(
                "Your session has expired. Please log in again."
            );

            return;

        }


        const user =
            await response.json();


        await showDashboard(
            user
        );

    }


    catch (error) {

        console.error(
            "Session restoration error:",
            error
        );


        showAuthScreen(
            "Unable to restore your session. Please log in again."
        );

    }

}


/* ============================================================
   START APPLICATION
============================================================ */

initializeApp();