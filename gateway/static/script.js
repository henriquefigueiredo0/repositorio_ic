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

// Seleciona o botao Iniciar
const botaoIniciar = document.getElementById("iniciar");

// Envia as configuracoes ao Flask
async function iniciarGateway() {

    const configuracao = {
        protocolo: protocolo.value,
        porta: Number(porta.value),
        parametro: parametro.value,
        ip_clp: document.getElementById("ip-clp").value
    };

    // Envia uma requisicao POST
    const resposta = await fetch("/iniciar", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify(configuracao)
    });

    // Le a resposta do servidor
    const resultado = await resposta.json();

    alert(resultado.mensagem);
}

// Executa a funcao quando o botao for clicado
botaoIniciar.addEventListener("click", iniciarGateway);
