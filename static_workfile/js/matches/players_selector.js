let selected_players = [];
let group_id = null;

// options for the group types
const group_types = {
    "01927d88-6878-7d0f-acbf-28c251fbc2b5": ["Remove"], // attack
    "01927d88-57ef-7339-a791-67cf856bfea1": ["Remove"], // defense
    "0192c7bb-c664-77fd-8a29-acde6f428c93": ["Remove", "Atack", "Defense"] // reserve
};

const typeIds= [
    "01927d88-6878-7d0f-acbf-28c251fbc2b5",
    "01927d88-57ef-7339-a791-67cf856bfea1",
    "0192c7bb-c664-77fd-8a29-acde6f428c93"
];

const groupIdsToTypeIds = {};

window.addEventListener("DOMContentLoaded", function() {
    fillTypeIDToGroupId()

    playerButtons();
});

function playerButtons() {
    // get all the elements with the class 'player'
    const players = document.getElementsByClassName("player");

    for (const player of players) {
        player.addEventListener("click", function() {
            const group_id_local = player.parentElement ? player.parentElement.id : null;
            
            if (group_id == group_id_local || group_id == null) {
                if (!selected_players.includes(player.id)) {
                    const player_id = player.id;

                    selected_players.push(player_id);
                    group_id = group_id_local;

                    highlightSelectedPlayer(player, selected_players);

                    showOptionsBar(group_id);
                } else {
                    const index = selected_players.indexOf(player.id);
                    selected_players.splice(index, 1);
                    if (selected_players.length === 0) {
                        group_id = null;
                    }

                    highlightSelectedPlayer(player, selected_players);

                    removeOptionsBar();
                }
            }
        });
    }
}

function highlightSelectedPlayer(player, selected_players) {
    if (selected_players.includes(player.id)) {
        player.style.backgroundColor = "lightblue";
    } else {
        player.style.backgroundColor = "white";
    }
}

function showOptionsBar(group_id) {
    if (selected_players.length === 1) {
        const optionsBar = document.createElement("div");
        optionsBar.classList.add("options-bar");
        optionsBar.id = "options-bar";

        console.log(group_id);
        console.log(groupIdsToTypeIds[group_id]);

        // add the buttons with the options
        const options = group_types[groupIdsToTypeIds[group_id]];

        console.log(options);

        for (const option of options) {
            const button = document.createElement("button");
            button.innerText = option;
            button.addEventListener("click", function() {
                if (option === "Remove") {
                    for (const player_id of selected_players) {
                        const player = document.getElementById(player_id);
                        player.style.backgroundColor = "white";
                    }
                    selected_players = [];
                    group_id = null;

                    removeOptionsBar();
                } else {
                    console.log("Change the group of the selected players to " + option);
                }
            });
            optionsBar.appendChild(button);
        }
        
        document.body.appendChild(optionsBar);

        // change the hight of the class 'scrollable' to make space for the options bar
        const scrollable = document.getElementsByClassName("scrollable")[0];
        scrollable.style.height = "calc(100vh - 208px)";
    }
}

function removeOptionsBar() {
    if (selected_players.length === 0) {
        const optionsBar = document.getElementById("options-bar");
        if (optionsBar) {
            optionsBar.remove();

            // change the hight of the class 'scrollable' to make space for the options bar
            const scrollable = document.getElementsByClassName("scrollable")[0];
            scrollable.style.height = "";
        }
    }
}

function fillTypeIDToGroupId() {
    for (const typeId of typeIds) {
        const group_id = document.getElementById(typeId).innerText;
        groupIdsToTypeIds[group_id] = typeId;
    }

    console.log(groupIdsToTypeIds);
}