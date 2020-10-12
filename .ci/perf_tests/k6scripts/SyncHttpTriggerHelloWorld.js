import { check } from "k6";
import { Rate } from "k6/metrics";
import http from "k6/http";

var HOSTNAME = __ENV.HOSTNAME || 'localhost';
var PORT = __ENV.PORT || '80';
var PROTOCOL = __ENV.PROTOCOL || (PORT === '80' ? 'http' : 'https');

// A custom metric to track failure rates
var failureRate = new Rate("check_failure_rate");

// Options
export let options = {
    stages: [
        // Linearly ramp up from 1 to 100 VUs during first minute
        { target: 100, duration: "30s" },
        // Hold at 100 VUs for the next 1 minutes and 15 seconds
        { target: 100, duration: "1m15s" },
        // Linearly ramp down from 100 to 0 50 VUs over the last 30 seconds
        { target: 0, duration: "15s" }
        // Total execution time will be ~2 minutes
    ],
    thresholds: {
        // We want the 95th percentile of all HTTP request durations to be less than 500ms
        "http_req_duration": ["p(50)<5000"]
        // Thresholds based on the custom metric we defined and use to track application failures
//        "check_failure_rate": [
//            // Global failure rate should be less than 1%
//            "rate<0.01",
//            // Abort the test early if it climbs over 5%
//            { threshold: "rate<=0.05", abortOnFail: true },
//        ],
    },
};

// Main function
export default function () {
    let response = http.get(`${PROTOCOL}://${HOSTNAME}:${PORT}/api/SyncHttpTriggerHelloWorld`);

    // check() returns false if any of the specified conditions fail
    let checkRes = check(response, {
        "status is 200": (r) => r.status === 200,
        // "content is present": (r) => r.body.indexOf("This HTTP triggered function executed successfully") !== -1,
    });

    // We reverse the check() result since we want to count the failures
    failureRate.add(!checkRes);
}