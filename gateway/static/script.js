
// Seleciona os elementos
const protocolo = document.getElementById("protocolo");
const porta = document.getElementById("porta");
const parametro = document.getElementById("parametro");
const labelParametro = document.getElementById("label-parametro");

const botaoIniciar = document.getElementById("iniciar");
const botaoParar = document.getElementById("parar");

const statusEsp = document.getElementById("status-esp");
const statusClp = document.getElementById("status-clp");
const distancia = document.getElementById("distancia");
const estadoBomba = document.getElementById("estado-bomba");
const ipClp = document.getElementById("ip-clp");

let operacaoEmAndamento = false;
let consultaEmAndamento = false;


// Atualiza os campos do protocolo
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


// Bloqueia os campos de configuracao
function bloquearConfiguracoes(bloquear) {
    protocolo.disabled = bloquear;
    porta.disabled = bloquear;
    parametro.disabled = bloquear;
    ipClp.disabled = bloquear;
}


// Atualiza os dados da pagina
function mostrarEstado(estado) {

    // Recupera o protocolo ativo
    if (estado.ativo && estado.protocolo) {
        if (protocolo.value !== estado.protocolo) {
            protocolo.value = estado.protocolo;
            atualizarProtocolo();
        }
    }

    statusEsp.textContent = estado.status_esp;
    statusClp.textContent = estado.status_clp;

    // Exibe apenas medicoes recentes
    if (estado.distancia === null) {
        distancia.textContent = "-- cm";
    } else {
        distancia.textContent =
            Number(estado.distancia).toFixed(2) + " cm";
    }

    // Ainda nao temos leitura do CLP
    if (estado.estado_bomba === null) {
        estadoBomba.textContent = "--";
    } else {
        estadoBomba.textContent = String(estado.estado_bomba);
    }

    if (!operacaoEmAndamento) {
        botaoIniciar.disabled = estado.ativo;
        botaoParar.disabled = !estado.ativo;
        bloquearConfiguracoes(estado.ativo);
    }
}


// Consulta o estado do Flask
async function consultarEstado() {

    if (consultaEmAndamento || operacaoEmAndamento) {
        return;
    }

    consultaEmAndamento = true;

    try {
        const resposta = await fetch("/estado", {
            cache: "no-store"
        });

        if (!resposta.ok) {
            throw new Error("Erro ao consultar o gateway.");
        }

        const estado = await resposta.json();
        mostrarEstado(estado);

    } catch (erro) {
        console.error("Erro de monitoramento:", erro);

        statusEsp.textContent = "Servidor indisponivel";
        statusClp.textContent = "Nao monitorado";
        distancia.textContent = "-- cm";
        estadoBomba.textContent = "--";

        // Evita comandos com estado desconhecido
        botaoIniciar.disabled = true;
        botaoParar.disabled = true;
        bloquearConfiguracoes(true);

    } finally {
        consultaEmAndamento = false;
    }
}


// Inicia o gateway
async function iniciarGateway() {

    if (operacaoEmAndamento) {
        return;
    }

    operacaoEmAndamento = true;
    botaoIniciar.disabled = true;
    botaoParar.disabled = true;

    const configuracao = {
        protocolo: protocolo.value,
        porta: Number(porta.value),
        parametro: parametro.value,
        ip_clp: ipClp.value
    };

    try {
        const resposta = await fetch("/iniciar", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(configuracao)
        });

        const resultado = await resposta.json();
        alert(resultado.mensagem);

    } catch (erro) {
        console.error("Erro ao iniciar:", erro);
        alert("Nao foi possivel comunicar com o Flask.");

    } finally {
        operacaoEmAndamento = false;
        await consultarEstado();
    }
}


// Para o gateway
async function pararGateway() {

    if (operacaoEmAndamento) {
        return;
    }

    operacaoEmAndamento = true;
    botaoIniciar.disabled = true;
    botaoParar.disabled = true;

    try {
        const resposta = await fetch("/parar", {
            method: "POST"
        });

        const resultado = await resposta.json();
        alert(resultado.mensagem);

    } catch (erro) {
        console.error("Erro ao parar:", erro);
        alert("Nao foi possivel comunicar com o Flask.");

    } finally {
        operacaoEmAndamento = false;
        await consultarEstado();
    }
}


// Configura os botoes
protocolo.addEventListener("change", atualizarProtocolo);
botaoIniciar.addEventListener("click", iniciarGateway);
botaoParar.addEventListener("click", pararGateway);


// Consulta o estado ao abrir a pagina
botaoIniciar.disabled = true;
botaoParar.disabled = true;
bloquearConfiguracoes(true);

consultarEstado();


// Atualiza a interface a cada segundo
setInterval(consultarEstado, 1000);
