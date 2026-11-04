// Seleciona os elementos da pagina
const protocolo = document.getElementById("protocolo");
const porta = document.getElementById("porta");
const parametro = document.getElementById("parametro");
const labelParametro = document.getElementById("label-parametro");

// Atualiza os campos conforme o protocolo escolhido
function atualizarProtocolo() {

    if (protocolo.value === "MQTT") {
        porta.value = 1883;
        parametro.value = "ic/esp/distancia";
        labelParametro.textContent = "Topico MQTT";
    }

    else if (protocolo.value === "OPCUA") {
        porta.value = 4840;
        parametro.value = "urn:gateway";
        labelParametro.textContent = "Namespace OPC UA";
    }
}

// Executa a funcao quando o protocolo muda
protocolo.addEventListener("change", atualizarProtocolo);
