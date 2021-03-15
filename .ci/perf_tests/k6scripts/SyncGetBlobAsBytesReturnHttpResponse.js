import { check } from "k6";
import { Rate } from "k6/metrics";
import http from "k6/http";

var HOSTNAME = __ENV.HOSTNAME || 'localhost';
var PORT = __ENV.PORT || '80';
var PROTOCOL = __ENV.PROTOCOL || (PORT === '80' ? 'http' : 'https');
var INPUT_FILENAME = 'Input_256MB'
var CONTENT_SIZE = 1024 * 1024 * 256; // 256 MB

// A custom metric to track failure rates
var failureRate = new Rate("check_failure_rate");

// Options
export let options = {
    stages: [
        // Linearly ramp up from 1 to 20 VUs during first minute
        { target: 20, duration: "1m" },
        // Hold at 20 VUs for the next 3 minutes and 45 seconds
        { target: 20, duration: "3m45s" },
        // Linearly ramp down from 20 to 0 VUs over the last 15 seconds
        { target: 0, duration: "15s" }
        // Total execution time will be ~5 minutes
    ],
    thresholds: {
        // We want the 95th percentile of all HTTP request durations to be less than 40s
        "http_req_duration": ["p(95)<40000"],
        // Thresholds based on the custom metric we defined and use to track application failures
        "check_failure_rate": [
            // Global failure rate should be less than 1%
            "rate<0.01",
            // Abort the test early if it climbs over 5%
            { threshold: "rate<=0.05", abortOnFail: true },
        ],
    },
};

// Setup function
// This will create a blob which will later be used as an input binding
export function setup() {
    let no_random_input = true;
    let url = `${PROTOCOL}://${HOSTNAME}:${PORT}/api/SyncPutBlobAsBytesReturnHttpResponse?content_size=${CONTENT_SIZE}&no_random_input=${no_random_input}&outfile=${INPUT_FILENAME}`;
    let response = http.get(url);

    // check() returns false if any of the specified conditions fail
    let checkRes = check(response, {
        "status is 200": (r) => r.status === 200,
        "content_size matches": (r) => r.json().content_size === CONTENT_SIZE,
    });
}

// Main function
export default function () {
    let url = `${PROTOCOL}://${HOSTNAME}:${PORT}/api/SyncGetBlobAsBytesReturnHttpResponse?infile=${INPUT_FILENAME}`;
    let response = http.get(url);

    // check() returns false if any of the specified conditions fail
    let checkRes = check(response, {
        "status is 200": (r) => r.status === 200,
        "content_size matches": (r) => r.json().content_size === CONTENT_SIZE,
    });

    // We reverse the check() result since we want to count the failures
    failureRate.add(!checkRes);
}
