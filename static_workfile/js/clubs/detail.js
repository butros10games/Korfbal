"use strict";

import { cleanDom } from "./common/common.js";
import { setupCarousel, updateMatches, updateTeam } from "./common/carousel";
import { initializeSocket, requestInitalData } from "./common/websockets";
import { setupFollowButton } from "./common/setup_follow_button.js";

let socket;
let team_id;
let user_id;
let WebSocket_url;
const infoContainer = document.getElementById("info-container");
const carousel = document.querySelector('.carousel');
const buttons = document.querySelectorAll('.button');

const regex = /([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})/;
const url = window.location.href;
const maxLength = 14;

window.addEventListener("DOMContentLoaded", function() {
    user_id = document.getElementById("user_id").innerText;
    const matches = regex.exec(url);
    if (matches) {
        team_id = matches[1];
        console.log(team_id);
    } else {
        console.log("No UUID found in the URL.");
    }

    WebSocket_url = "wss://" + window.location.host + "/ws/club/" + team_id + "/";
    socket = initializeSocket(WebSocket_url, onMessageReceived);

    socket.onopen = function() {
        console.log("WebSocket connection established, sending initial data...");
        requestInitalData(".button.active", socket);
    };

    setupCarousel(carousel, buttons, socket);
    setupFollowButton(user_id, socket);
});

function onMessageReceived(event) {
    const data = JSON.parse(event.data);
    console.log(data);

    switch(data.command) {
        case "wedstrijden":
            cleanDom(infoContainer);

            updateMatches(data, maxLength, infoContainer); // imported from common/updateMatches.js
            break;
        
        case "teams":
            cleanDom(infoContainer);

            updateTeam(data, infoContainer); // imported from common/updateTeam.js
            break;
    }
}
