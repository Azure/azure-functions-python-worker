import { check } from "k6";
import { Rate } from "k6/metrics";
import http from "k6/http";
import { randomIntBetween } from "https://jslib.k6.io/k6-utils/1.0.0/index.js";

var HOSTNAME = __ENV.HOSTNAME || 'localhost';
var PORT = __ENV.PORT || '80';
var PROTOCOL = __ENV.PROTOCOL || (PORT === '80' ? 'http' : 'https');

// A custom metric to track failure rates
var failureRate = new Rate("check_failure_rate");

// Options
export let options = {
    stages: [
        // Linearly ramp up from 1 to 50 VUs during first minute
        { target: 50, duration: "1m" },
        // Hold at 50 VUs for the next 3 minutes and 45 seconds
        { target: 50, duration: "3m45s" },
        // Linearly ramp down from 50 to 0 VUs over the last 15 seconds
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

// Main function
export default function () {
    let content_size = 1024 * 1024 * 256; // 256 MB
    let no_random_input = true;
    let outfile = randomIntBetween(1,500000);
    let url = `${PROTOCOL}://${HOSTNAME}:${PORT}/api/SyncPutBlobAsBytesReturnHttpResponse?content_size=${content_size}&no_random_input=${no_random_input}&outfile=${outfile}`;
    let response = http.get(url);

    // check() returns false if any of the specified conditions fail
    let checkRes = check(response, {
        "status is 200": (r) => r.status === 200,
        "content_size matches": (r) => r.json().content_size === content_size,
    });

    // We reverse the check() result since we want to count the failures
    failureRate.add(!checkRes);
}
