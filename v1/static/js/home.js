window.add_working_model = function(){
    let blur = document.createElement("div");
    blur.setAttribute("style", "user-select:none;position: fixed; top:0px; left:0px; height:100%; width:100%; background:rgba(0,0,0,0.15); z-index: 9999999999999");

    let css = document.createElement("style");
    css.innerHTML = `.animation-container {
        display: flex;
        position: absolute;
        bottom: 50%;
        right: 50%;
        align-items: center;
        text-align: center;
        transform: rotate(90deg) translate(-50%, -50%);
    }

    .letter.X {
        animation: move-letter_x 4s ease-in-out infinite;
        animation-iteration-count: infinite;
    }
    .letter.Y {
        animation: move-letter_y 4s ease-in-out infinite;
        animation-iteration-count: infinite;
    }
    .letter.Z {
        animation: move-letter_z 4s ease-in-out infinite;
        animation-iteration-count: infinite;
    }

    @keyframes move-letter_x {
        0% {
            -webkit-transform: rotate(0deg) translateX(150px) rotate(0deg);
        }
        50% {
            -webkit-transform: rotate(360deg) translateX(20px) rotate(-360deg);
        }
        100% {
            -webkit-transform: rotate(0deg) translateX(150px) rotate(0deg);
        }
    }
    @keyframes move-letter_y {
        0% {
            -webkit-transform: rotate(360deg) translateX(150px) rotate(-360deg);
        }
        50% {
            -webkit-transform: rotate(0deg) translateX(80px) rotate(0deg);
        }
        100% {
            -webkit-transform: rotate(360deg) translateX(150px) rotate(-360deg);
        }
    }
    @keyframes move-letter_z {
        0% {
            -webkit-transform: rotate(0deg) translateX(150px) rotate(0deg);
        }
        50% {
            -webkit-transform: rotate(360deg) translateX(140px) rotate(-360deg);
        }
        100% {
            -webkit-transform: rotate(0deg) translateX(150px) rotate(0deg);
        }  
    }`;

    let animation_container = document.createElement("div");
    animation_container.className = "animation-container";
    animation_container.innerHTML = `<div class="letter X" style='color:white'>🔴</div>
                                    <div class="letter Y" style='color:white'>🟢</div>
                                    <div class="letter Z" style='color:white'>🔵</div>`;

    blur.append(animation_container);
    document.body.append(blur);
    document.body.append(css);
    return [blur, css];
}
window.post = function(url, data) {
    return fetch(url, {method: "POST", headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)});
}
async function restart(id){
    let t = window.add_working_model();
    let data = await (await window.post("/api/restart", {"id":id.split("/")[1]})).json();
    if(data.success){
        location.reload();
    }else{
        document.body.removeChild(t[0]);
        document.body.removeChild(t[1]);
        window.messagebox({type: 0, message: "We were unable to restart the machine.\nTry again"});
    }
}
async function start(id){
    let t = window.add_working_model();
    let data = await (await window.post("/api/start", {"id":id.split("/")[1]})).json();
    if(data.success){
        location.reload();
    }else{
        document.body.removeChild(t[0]);
        document.body.removeChild(t[1]);
        window.messagebox({type: 0, message: "We were unable to start the machine.\nTry again"});
    }
}
async function stop(id){
    let t = window.add_working_model();
    let data = await (await window.post("/api/stop", {"id":id.split("/")[1]})).json();
    if(data.success){
        location.reload();
    }else{
        document.body.removeChild(t[0]);
        document.body.removeChild(t[1]);
        window.messagebox({type: 0, message: "We were unable to stop the machine.\nTry again"});
    }
}
async function remove(id){
    let tmp = window.promptbox({message: "Type '" + id + "' in the box bellow to remove it"});
    if(tmp.trim() == id){
        let t = window.add_working_model();
        let data = await (await window.post("/api/delete", {"id":id.split("/")[1]})).json();
        if(data.success){
            location.reload();
        }else{
            document.body.removeChild(t[0]);
            document.body.removeChild(t[1]);
            window.messagebox({type: 0, message: "We were unable to delete the machine.\nTry again"});
        }
    }
}
function open_console(id){
    window.open(`${location.protocol}/xterm?containerid=${id.split("/")[1]}`, "_blank");
}
var script = document.createElement("script");
script.src = "/static/js/message_popups.js";
document.body.append(script);