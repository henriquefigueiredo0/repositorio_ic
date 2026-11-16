
// Enderecos da API Flask
const API_REGRAS = "/api/regras";
const API_SERVICOS = "/api/servicos";

// Guarda as regras recuperadas do servidor
let regras = [];
let atualizando = false;

// Referencias aos principais elementos da pagina
const corpoTabela = document.getElementById("corpo-tabela");
const janelaRegra = document.getElementById("janela-regra");
const formulario = document.getElementById("formulario-regra");
const mensagem = document.getElementById("mensagem");


// Envia requisicoes HTTP e interpreta as respostas
async function requisicao(url, metodo = "GET", dados = null) {
    const opcoes = { method: metodo };

    if (dados !== null) {
        opcoes.headers = { "Content-Type": "application/json" };
        opcoes.body = JSON.stringify(dados);
    }

    const resposta = await fetch(url, opcoes);
    const texto = await resposta.text();

    let resultado = {};

    if (texto) {
        try {
            resultado = JSON.parse(texto);
        } catch {
            throw new Error("O servidor retornou uma resposta invalida.");
        }
    }

    if (!resposta.ok) {
        throw new Error(resultado.mensagem || resultado.erro || `Erro HTTP ${resposta.status}`);
    }

    return resultado;
}


// Mostra mensagens de sucesso ou erro na pagina
function mostrarMensagem(texto, erro = false) {
    mensagem.textContent = texto;
    mensagem.className = erro ? "mensagem erro" : "mensagem sucesso";
}


// Atualiza o indicador visual de um servico
function atualizarIndicador(nome, conectado, ativo = true) {
    const indicador = document.getElementById(`indicador-${nome}`);
    const texto = document.getElementById(`status-${nome}`);

    indicador.className = "indicador";

    if (!ativo) {
        indicador.classList.add("desligado");
        texto.textContent = "Desabilitado";
    } else if (conectado) {
        indicador.classList.add("ligado");
        texto.textContent = "Disponível";
    } else {
        indicador.classList.add("desligado");
        texto.textContent = "Indisponível";
    }
}


// Consulta a situacao dos servicos de comunicacao
async function carregarServicos() {
    try {
        const servicos = await requisicao(API_SERVICOS);

        atualizarIndicador("mqtt", servicos.mqtt);
        atualizarIndicador("opcua", servicos.opcua);
        atualizarIndicador("clp", servicos.clp_habilitado, servicos.clp_habilitado);

    } catch {
        atualizarIndicador("mqtt", false);
        atualizarIndicador("opcua", false);
        atualizarIndicador("clp", false);
    }
}


// Cria uma celula de texto sem interpretar HTML recebido
function criarCelula(linha, valor, classe = "") {
    const celula = document.createElement("td");

    celula.textContent = valor === null || valor === undefined ? "—" : String(valor);

    if (classe) {
        celula.className = classe;
    }

    linha.appendChild(celula);
    return celula;
}


// Cria um botao de acao para determinada regra
function criarBotao(texto, classe, acao) {
    const botao = document.createElement("button");

    botao.type = "button";
    botao.textContent = texto;
    botao.className = `botao pequeno ${classe}`;
    botao.addEventListener("click", acao);

    return botao;
}


// Apresenta o ultimo valor processado pela regra
function formatarValor(valor) {
    if (valor === null || valor === undefined) {
        return "—";
    }

    if (typeof valor === "boolean") {
        return valor ? "TRUE" : "FALSE";
    }

    if (typeof valor === "object") {
        return JSON.stringify(valor);
    }

    return String(valor);
}


// Constrói a tabela com todas as regras cadastradas
function mostrarRegras() {
    corpoTabela.replaceChildren();

    const total = regras.length;
    document.getElementById("contador-regras").textContent = `${total} ${total === 1 ? "regra" : "regras"}`;

    if (total === 0) {
        const linha = document.createElement("tr");
        const celula = criarCelula(linha, 'Nenhuma regra cadastrada. Clique em "Adicionar".', "tabela-vazia");

        celula.colSpan = 11;
        corpoTabela.appendChild(linha);
        return;
    }

    for (const regra of regras) {
        const linha = document.createElement("tr");

        criarCelula(linha, regra.protocolo);
        criarCelula(linha, regra.direcao === "SERVIDOR_PARA_CLP" ? "Servidor → CLP" : "CLP → Servidor");
        criarCelula(linha, regra.porta);
        criarCelula(linha, regra.topico);
        criarCelula(linha, regra.parametro);
        criarCelula(linha, regra.tipo);
        criarCelula(linha, regra.ip_clp);
        criarCelula(linha, regra.memoria);
        criarCelula(linha, formatarValor(regra.ultimo_valor), "coluna-valor");

        // Mostra a situacao informada pelo motor de regras
        const celulaStatus = document.createElement("td");
        const status = document.createElement("span");

        // Diferencia erros de regras ativas e desativadas
        status.className = regra.erro ? "status erro" : `status ${regra.ativo ? "ativo" : "inativo"}`;
        
        status.textContent = regra.ativo ? (regra.situacao || "Ativa") : "Desativada";

        if (regra.erro) {
            status.title = regra.erro;
        }

        celulaStatus.appendChild(status);
        linha.appendChild(celulaStatus);

        // Cada regra tem suas proprias acoes
        const celulaAcoes = document.createElement("td");
        const grupo = document.createElement("div");
        grupo.className = "grupo-acoes";

        const textoAtivar = regra.ativo ? "Desativar" : "Ativar";

        grupo.appendChild(criarBotao(textoAtivar, "secundario", () => alterarAtivacao(regra)));
        grupo.appendChild(criarBotao("Editar", "secundario", () => abrirFormulario(regra)));
        grupo.appendChild(criarBotao("Excluir", "perigo", () => excluirRegra(regra)));

        celulaAcoes.appendChild(grupo);
        linha.appendChild(celulaAcoes);
        corpoTabela.appendChild(linha);
    }
}


// Recupera as regras e seus valores atuais
async function carregarRegras() {
    const resposta = await requisicao(API_REGRAS);

    if (!Array.isArray(resposta)) {
        throw new Error("A API de regras deve retornar uma lista.");
    }

    regras = resposta;
    mostrarRegras();
}


// Atualiza a tabela e os indicadores periodicamente
async function atualizarPagina() {
    if (atualizando) {
        return;
    }

    atualizando = true;

    try {
        await Promise.all([carregarRegras(), carregarServicos()]);
    } catch (erro) {
        mostrarMensagem(`Falha ao atualizar a interface: ${erro.message}`, true);
    } finally {
        atualizando = false;
    }
}


// Atualiza os campos conforme o protocolo e a direcao
function atualizarCampos() {
    const protocolo = document.getElementById("protocolo").value;
    const direcao = document.getElementById("direcao").value;
    const tipo = document.getElementById("tipo").value;

    const campoTopico = document.getElementById("topico");
    const campoMemoria = document.getElementById("memoria");
    const campoPorta = document.getElementById("porta");

    const opcua = protocolo === "OPCUA";
    const lendoClp = direcao === "CLP_PARA_SERVIDOR";

    document.getElementById("rotulo-topico").textContent = opcua ? "Identificador do nó OPC UA" : "Tópico MQTT";

    campoTopico.placeholder = opcua ? "Ex.: esp32/distancia" : "Ex.: ic/esp/distancia";
    campoMemoria.placeholder = tipo === "BOOL" ? (lendoClp ? "M20.0 ou Q0.3" : "M20.0") : { REAL: "MD10", INT: "MW20", STRING: "MB30" }[tipo];

    // As portas correspondem aos servicos permanentes do gateway
    campoPorta.value = opcua ? 4840 : 1883;
    campoPorta.readOnly = true;

    // Tamanho de STRING e intervalo de leitura sao campos condicionais
    document.getElementById("campo-tamanho-string").classList.toggle("oculto", tipo !== "STRING");
    document.getElementById("campo-intervalo").classList.toggle("oculto", !lendoClp);

    document.getElementById("ajuda-regra").textContent = opcua
        ? "Informe o nome lógico do nó OPC UA. Os nós serão criados no servidor do gateway."
        : "Informe o tópico MQTT exato. O parâmetro identifica um campo dentro do objeto 'dados' do JSON.";
}


// Abre o formulario para criar ou editar uma regra
function abrirFormulario(regra = null) {
    formulario.reset();

    document.getElementById("regra-id").value = regra ? regra.id : "";
    document.getElementById("titulo-formulario").textContent = regra ? "Editar regra" : "Adicionar regra";

    document.getElementById("protocolo").value = regra?.protocolo || "MQTT";
    document.getElementById("direcao").value = regra?.direcao || "SERVIDOR_PARA_CLP";
    document.getElementById("tipo").value = regra?.tipo || "REAL";

    document.getElementById("topico").value = regra?.topico || "";
    document.getElementById("parametro").value = regra?.parametro || "";
    document.getElementById("ip-clp").value = regra?.ip_clp || "";
    document.getElementById("memoria").value = regra?.memoria || "";
    document.getElementById("tamanho-string").value = regra?.tamanho_string ?? 32;
    document.getElementById("intervalo-ms").value = regra?.intervalo_ms ?? 200;

    atualizarCampos();
    janelaRegra.showModal();
}


// Fecha o formulario sem salvar as alteracoes
function fecharFormulario() {
    janelaRegra.close();
}


// Reune os valores do formulario para enviar ao Flask
function obterDadosFormulario() {
    return {
        protocolo: document.getElementById("protocolo").value,
        direcao: document.getElementById("direcao").value,
        porta: Number(document.getElementById("porta").value),
        topico: document.getElementById("topico").value.trim(),
        parametro: document.getElementById("parametro").value.trim(),
        tipo: document.getElementById("tipo").value,
        ip_clp: document.getElementById("ip-clp").value.trim(),
        memoria: document.getElementById("memoria").value.trim().toUpperCase(),
        tamanho_string: Number(document.getElementById("tamanho-string").value),
        intervalo_ms: Number(document.getElementById("intervalo-ms").value),
        ativo: false
    };
}


// Cria uma regra nova ou salva a edicao de uma existente
async function salvarRegra(evento) {
    evento.preventDefault();

    const id = document.getElementById("regra-id").value;
    const dados = obterDadosFormulario();

    // Uma edicao preserva o estado ativo da regra
    if (id) {
        const regraAnterior = regras.find(regra => String(regra.id) === id);
        dados.ativo = regraAnterior?.ativo ?? false;
    }

    const botao = document.getElementById("botao-salvar");
    botao.disabled = true;

    try {
        if (id) {
            await requisicao(`${API_REGRAS}/${id}`, "PUT", dados);
        } else {
            await requisicao(API_REGRAS, "POST", dados);
        }

        fecharFormulario();
        await carregarRegras();
        mostrarMensagem(id ? "Regra atualizada." : "Regra cadastrada.");

    } catch (erro) {
        mostrarMensagem(`Erro ao salvar: ${erro.message}`, true);

    } finally {
        botao.disabled = false;
    }
}


// Ativa ou desativa somente a regra selecionada
async function alterarAtivacao(regra) {
    try {
        await requisicao(`${API_REGRAS}/${regra.id}/ativar`, "POST", { ativo: !regra.ativo });

        await carregarRegras();
        mostrarMensagem(regra.ativo ? "Regra desativada." : "Regra ativada.");

    } catch (erro) {
        mostrarMensagem(`Erro ao alterar regra: ${erro.message}`, true);
    }
}


// Exclui uma regra apos confirmacao do usuario
async function excluirRegra(regra) {
    if (!confirm(`Excluir a regra ${regra.id} (${regra.parametro})?`)) {
        return;
    }

    try {
        await requisicao(`${API_REGRAS}/${regra.id}`, "DELETE");

        await carregarRegras();
        mostrarMensagem("Regra excluída.");

    } catch (erro) {
        mostrarMensagem(`Erro ao excluir: ${erro.message}`, true);
    }
}


// Eventos associados aos controles da pagina
document.getElementById("botao-adicionar").addEventListener("click", () => abrirFormulario());
document.getElementById("botao-fechar").addEventListener("click", fecharFormulario);
document.getElementById("botao-cancelar").addEventListener("click", fecharFormulario);

document.getElementById("protocolo").addEventListener("change", atualizarCampos);
document.getElementById("direcao").addEventListener("change", atualizarCampos);
document.getElementById("tipo").addEventListener("change", atualizarCampos);

formulario.addEventListener("submit", salvarRegra);


// Faz a primeira consulta e continua atualizando a cada segundo
atualizarPagina();
setInterval(atualizarPagina, 1000);
