// run when dom is loaded
let socket;
let team_id;
let user_id;
let WebSocket_url;
let infoContainer = document.getElementById("info-container");
let carousel = document.querySelector('.carousel');
let buttons = document.querySelectorAll('.button');

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

    WebSocket_url = "wss://" + window.location.host + "/ws/teams/" + team_id + "/";
    socket = initializeSocket(WebSocket_url, onMessageReceived);

    socket.onopen = function() {
        console.log("WebSocket connection established, sending initial data...");
        requestInitalData(".button.active", socket, { 'user_id': user_id });
    };

    setupCarousel(carousel, buttons, { 'user_id': user_id }, 'team_stats');
    setupFollowButton()
});

function onMessageReceived(event) {
    const data = JSON.parse(event.data);
    console.log(data);

    switch(data.command) {
        case "wedstrijden":
            cleanDom(infoContainer);

            updateMatches(data); // imported from common/updateMatches.js
            break;
        
        case "goal_stats":
            cleanDom(infoContainer);

            UpdateStatastics(data.data);
            break;

        case "spelers":
            cleanDom(infoContainer);
            
            updatePlayers(data);
            break;
    }
}

function UpdateStatastics(data) {
    const stats = data.stats;

    const statsContainer = document.createElement("div");
    statsContainer.classList.add("stats-container");

    if (stats) {
        // Check if the buttons already exist and if they exist, skip the creation of the buttons
        if (!document.querySelector(".stat-selector-button")) {
            cleanDom(infoContainer);

            const statSelectorButtonField = document.createElement("div");
            statSelectorButtonField.classList.add("flex-row");
            statSelectorButtonField.style.justifyContent = "space-around";
            statSelectorButtonField.style.margin = "12px";
            statSelectorButtonField.style.width = "calc(100% - 24px)";

            const buttonTypes = [
                { name: 'generaal', type: 'general' },
                { name: 'verloop', type: 'progression' },
                { name: 'spelers', type: 'player_stats' }
            ];

            buttonTypes.forEach(type => {
                const button = document.createElement("button");
                button.classList.add("stat-selector-button");

                // add to the first button a active class
                if (type.type == 'general') {
                    button.classList.add("active");
                }

                button.innerHTML = type.name;
                button.addEventListener('click', function() {
                    socket.send(JSON.stringify({
                        'command': 'get_stats',
                        'user_id': user_id,
                        'data_type': type.type
                    }));

                    // add active class to the button and remove it by the other buttons
                    const buttons = document.querySelectorAll(".stat-selector-button");
                    buttons.forEach((button) => {
                        button.classList.remove("active");
                    });
                    this.classList.add("active");
                });

                statSelectorButtonField.appendChild(button);
            });

            statsContainer.appendChild(statSelectorButtonField);
        }

        // Check if there is already a dataField and if there is a field delete it
        if (document.getElementById("dataField")) {
            document.getElementById("dataField").remove();
        }

        console.log(data);

        if (data.type == "general") {
            const goals_container = document.createElement("div");
            goals_container.classList.add("flex-column");
            goals_container.id = "dataField";
            goals_container.style.width = "calc(100% - 24px)";
            goals_container.style.padding = "12px";

            const row_1 = document.createElement("div");
            row_1.classList.add("flex-row");
            row_1.style.justifyContent = "space-around";
            row_1.style.width = "100%";
            row_1.style.marginBottom = "24px";

            const total_score_container = document.createElement("div");
            total_score_container.classList.add("flex-column");
            total_score_container.style.width = "144px";

            const total_score = document.createElement("p");
            total_score.style.margin = "0";
            total_score.style.fontSize = "14px";
            total_score.innerHTML = "Totaal punten";

            const total_score_data = document.createElement("p");
            total_score_data.style.margin = "0";
            total_score_data.innerHTML = stats.goals_for + '/' + stats.goals_against;

            total_score_container.appendChild(total_score);
            total_score_container.appendChild(total_score_data);

            row_1.appendChild(total_score_container);

            goals_container.appendChild(row_1);

            // Create a container for goal stats per type
            const goal_stats_container = document.createElement("div");
            goal_stats_container.classList.add("flex-row");
            goal_stats_container.style.width = "100%";
            goal_stats_container.style.marginTop = "12px";
            goal_stats_container.style.flexWrap = "wrap";
            goal_stats_container.style.justifyContent = "space-around";

            // Iterate through goal_stats object
            for (const goalType of stats.goal_types) {
                console.log(goalType);
                if (stats.team_goal_stats.hasOwnProperty(goalType.name)) {
                    const goalStat = stats.team_goal_stats[goalType.name];

                    // Create a div for each goal type's stats
                    const goal_type_container = document.createElement("div");
                    goal_type_container.classList.add("flex-column");
                    goal_type_container.style.marginBottom = "12px";
                    goal_type_container.style.width = "104px";

                    const goal_type_name = document.createElement("p");
                    goal_type_name.style.margin = "0";
                    goal_type_name.style.fontSize = "14px";
                    goal_type_name.innerHTML = goalType.name;

                    const goals_data = document.createElement("p");
                    goals_data.style.margin = "0";
                    goals_data.innerHTML = goalStat.goals_by_player + "/" + goalStat.goals_against_player;

                    goal_type_container.appendChild(goal_type_name);
                    goal_type_container.appendChild(goals_data);

                    goal_stats_container.appendChild(goal_type_container);
                }
            }

            goals_container.appendChild(goal_stats_container);
            statsContainer.appendChild(goals_container);
        } else if (data.type == "player_stats") {
            // Creating the player selector field
            const playerSelectorField = document.createElement("div");
            playerSelectorField.classList.add("flex-column");
            playerSelectorField.id = "dataField";
            playerSelectorField.style.margin = "24px 12px 0 12px";
            playerSelectorField.style.width = "calc(100% - 24px)";

            // Create a legend for the player stats
            const legend = document.createElement("div");
            legend.classList.add("flex-row");
            legend.style.justifyContent = "space-between";
            legend.style.marginBottom = "12px";
            legend.style.borderBottom = "1px solid #ccc";
            legend.style.paddingBottom = "12px";

            const name = document.createElement("p");
            name.innerHTML = "Naam";
            name.style.margin = "0";
            name.style.fontSize = "14px";

            const score = document.createElement("p");
            score.classList.add("flex-center");
            score.innerHTML = "Score";
            score.style.width = "80px";
            score.style.margin = "0";
            score.style.fontSize = "14px";
            score.style.marginLeft = "auto";
            score.style.marginRight = "12px";

            const shots = document.createElement("p");
            shots.classList.add("flex-center");
            shots.innerHTML = "Schoten";
            shots.style.width = "80px";
            shots.style.margin = "0";
            shots.style.fontSize = "14px";

            legend.appendChild(name);
            legend.appendChild(score);
            legend.appendChild(shots);

            playerSelectorField.appendChild(legend);

            stats.player_stats.forEach(player => {
                const playerDataDiv = document.createElement("div");
                playerDataDiv.classList.add("flex-row");
                playerDataDiv.style.justifyContent = "space-between";
                playerDataDiv.style.marginBottom = "12px";
                playerDataDiv.style.borderBottom = "1px solid #ccc";
                playerDataDiv.style.paddingBottom = "12px";

                const playerName = document.createElement("p");
                playerName.innerHTML = truncateMiddle(player.username, 20);
                playerName.style.margin = "0";
                playerName.style.fontSize = "14px";

                const playerScore = document.createElement("p");
                playerScore.classList.add("flex-center");
                playerScore.innerHTML = player.goals_for + " / " + player.goals_against;
                playerScore.style.width = "80px";
                playerScore.style.margin = "0";
                playerScore.style.fontSize = "14px";
                playerScore.style.marginLeft = "auto";
                playerScore.style.marginRight = "12px";

                const playerShots = document.createElement("p");
                playerShots.classList.add("flex-center");
                playerShots.innerHTML = player.shots_for + " / " + player.shots_against;
                playerShots.style.width = "80px";
                playerShots.style.margin = "0";
                playerShots.style.fontSize = "14px";

                playerDataDiv.appendChild(playerName);
                playerDataDiv.appendChild(playerScore);
                playerDataDiv.appendChild(playerShots);

                playerSelectorField.appendChild(playerDataDiv);
            });

            statsContainer.appendChild(playerSelectorField);
        }
    } else {
        const textElement = document.createElement("p");
        textElement.classList.add("flex-center");
        textElement.innerHTML = "<p>Geen statistieken gevonden.</p>";

        statsContainer.appendChild(textElement);
    }

    infoContainer.appendChild(statsContainer);
}

function updatePlayers(data) {
    if (data.spelers.length > 0) {
        infoContainer.classList.add("flex-start-wrap");
        
        for (const element of data.spelers) {
            const player_container = document.createElement("a");
            player_container.href = element.get_absolute_url;
            player_container.style.textDecoration = "none";
            player_container.style.color = "#000";
            player_container.classList.add("player-container");

            const player_profile_pic = document.createElement("img");
            player_profile_pic.classList.add("player-profile-pic");
            player_profile_pic.src = element.profile_picture;
            player_profile_pic.style.objectFit = "cover";

            player_container.appendChild(player_profile_pic);

            const player_name = document.createElement("p");
            player_name.classList.add("player-name");
            player_name.style.fontSize = "14px";

            const PlayerName = truncateMiddle(element.name, 22);

            player_name.innerHTML = PlayerName;

            player_container.appendChild(player_name);

            infoContainer.appendChild(player_container);
        }
    } else {
        infoContainer.classList.add("flex-center");
        infoContainer.innerHTML = "<p style='text-align: center;'>Er zijn nog geen spelers toegevoegd</p>";
    }
}