# Projeto Thoth — Plano de Implementação de Sistema Robótico Inteligente Multiagente

**Mão protética HACKberry + Arquitetura Multiagente Agno AI + Visão Computacional + Voz**

> Universidade Federal do Rio Grande do Sul (UFRGS) · Enfitec Jr. (Engenharia Física) · CTA — Centro de Tecnologia Acadêmica (IF-UFRGS)
> Documento técnico de planejamento · Versão 1.0

---

## 0. Sumário Executivo

Este documento é um plano de implementação de nível de laboratório de pesquisa para transformar a **mão protética HACKberry** (projeto open-source da exiii Inc. / Mission ARM Japan, hoje sob curadoria da Mission ARM Japan) em um **assistente robótico físico inteligente**, capaz de:

- **observar** o ambiente por visão computacional (detecção de pessoas, rostos, identidades e gestos);
- **conversar** naturalmente e **responder a comandos de voz** com escuta contínua e palavra de ativação;
- **executar gestos físicos** com a mão (preensão, apontar, pinça, "apertar a mão");
- **reconhecer indivíduos** conhecidos (ex.: cumprimentar automaticamente um professor);
- **decidir** com base em estímulos visuais e auditivos;
- operar de forma **modular** através de **agentes especializados** orquestrados pelo framework **Agno AI**.

A espinha dorsal cognitiva combina três provedores de IA por papel: **Claude** (planejamento, raciocínio, coordenação de agentes e diálogo), **Groq** (Speech-to-Text, análise multimodal de imagens e inferência de baixa latência) e **Cerebras** (inferência de altíssima velocidade complementar). A ponte com o hardware é um **firmware Arduino customizado** com protocolo serial seguro, comandado por um **cliente Python assíncrono**.

### Como ler este documento

| Seção | Conteúdo |
|------|----------|
| **0. Sumário Executivo** | Esta seção + a reconciliação de hardware (leitura obrigatória). |
| **1. Arquitetura Geral** | Camadas, catálogo de agentes, event bus, fluxogramas, tecnologias por camada. |
| **2. Estrutura de Pastas** | Árvore completa do projeto Python com Agno e arquivos de configuração. |
| **3. Roadmap de Desenvolvimento** | 8 fases com tarefas, entregáveis, critérios de aceite, riscos e cronograma. |
| **4. Tecnologias** | Justificativa de cada biblioteca, alternativas e atribuição de modelos de IA por papel. |
| **5. Exemplos de Código** | Firmware, cliente serial, webcam, reconhecimento facial, STT, event bus, agentes Agno e primitivas de movimento. |
| **6. Segurança** | Anticolisão, limites de movimento, parada de emergência, proteção dos servos e segurança da IA. |
| **7. Escalabilidade Futura** | Mais DOF, base móvel, LLM local, ROS2, manipulação e autonomia avançada. |

---

## 0.1 Reconciliação de Hardware × Objetivos — **leitura obrigatória**

> Este é o ponto técnico mais importante do plano. A descrição inicial do projeto trata o equipamento como um **"braço robótico 3DOF"** genérico que apontaria e levantaria. O manual oficial mostra que o hardware é, na verdade, a **mão protética HACKberry** — e isso muda fundamentalmente o que é viável.

### O que o hardware realmente é

A HACKberry **não é um braço posicionador**: é uma **mão protética** impressa em 3D. Os **"3 graus de liberdade"** correspondem a **três servomotores que controlam a preensão dos dedos**, e **não** ao posicionamento da mão no espaço:

| DOF | Servo | Função | Pino (Hand Board Mk2) |
|-----|-------|--------|------------------------|
| 1 | Servo grande | Flexão do **dedo indicador** | **D5** |
| 2 | Servo pequeno | Flexão dos **três dedos** (médio, anelar, mínimo) | **D6** |
| 3 | Servo pequeno | **Polegar** (abdução/rotação) | **D9** |

- **Microcontrolador:** Arduino Nano (ATmega328P-AU) na placa *HACKberry Hand Board Mk2* (a Mk1 usava Arduino Micro). Comunicação com o PC por **micro-USB**.
- **Sensor:** fotorrefletor de pressão **ou** EMG (MyoWare, 2 canais) na entrada **A1 (SENS)**.
- **Pulso:** ajustável **apenas manualmente**, em incrementos de **90°** (pronação/supinação, flexão/extensão, desvio radial/ulnar). **Não há motor** no pulso nem no antebraço/braço.
- **Energia:** bateria Li-ion **7,2 V / 2200 mAh**; entrada recomendada 7–12 V. Proteção de corrente **500 mA (PPTC)** nos servos do indicador e dos três dedos; **o servo do polegar não é protegido por PPTC**.

### Mapeamento dos comandos de voz desejados ao hardware real

| Comando desejado | Viável na HACKberry? | Como |
|------------------|----------------------|------|
| **"Aperte minha mão"** | ✅ **Sim** | Fechamento suave e controlado da preensão (gesto *shake*). |
| **"Aponte para mim"** | ⚠️ **Parcial** | A mão **forma** o gesto de apontar (indicador estendido + demais flexionados), mas **não consegue se reorientar** para mirar uma pessoa sem um braço posicionador. |
| **"Levante o braço"** | ❌ **Não (sem hardware adicional)** | Exige atuadores de ombro/cotovelo. Tratado como evolução na **Seção 7.1**. |
| **"Quem está na sala?"** | ✅ **Sim** | Depende apenas de visão computacional; independe do braço. |

### Consequência arquitetural decisiva

O **firmware nativo** da HACKberry é **autônomo**: lê o sensor (pressão ou EMG) e aciona os servos em malha fechada, **sem expor uma API serial de comandos**. Para que os agentes de IA controlem a mão a partir do PC, é **obrigatório** desenvolver um **firmware customizado** que:

1. aceite **comandos seriais** (gestos nomeados + ângulos por servo);
2. preserve os **limites de segurança nativos** (`outThumbMax`, `outIndexMax`, `outOtherMax` e o limite de corrente);
3. implemente **watchdog**, **slew-rate** e **parada de emergência**.

Esse firmware é o **marco crítico da Fase 2** (ver Seção 3) e está especificado por completo na **Seção 5.1**. Recomenda-se manter **dois modos**: *host-controlled* (comandado pela IA) e *autônomo/EMG* (o comportamento protético original), selecionáveis — preservando o propósito assistivo do projeto.

### Licenciamento (atenção)

- **Firmware** (Arduino sketch) da HACKberry: **GPLv3** — derivados do firmware herdam a GPLv3.
- **Hardware / modelos 3D / placas:** **Creative Commons BY-NC-SA 4.0** — uso **não-comercial**, atribuição e compartilhamento igual. Para uso comercial, contatar a exiii/Mission ARM Japan.

---
