# 🤖 AsyncBOT

Um bot modular para **Discord**, desenvolvido com `discord.py`, projetado para servidores que buscam **organização, automação e diversão**.
---

## Recursos Principais

- **/duelo** — Mini-jogo com rodadas e animações.
- **Canais de voz automáticos** — cria e apaga salas conforme o uso.
- **Boas-vindas personalizadas** — mensagens com avatar e frases místicas.
- **Gerenciamento via slash commands** (`/load`, `/unload`, `/addadmin`, etc).
- **Status rotativo** — muda automaticamente as frases de presença.
- **Arquitetura modular** — fácil de expandir com novas cogs.

---

## Estrutura de Pastas

```
AsyncBOT/
├── bot.py                  # Núcleo principal
├── cogs/
|   ├── __init__.py
│   ├── core.py             # Sistema de admins e cogs
│   ├── duelo.py            # Duelo interativo
│   ├── ping.py             # Teste de latência
│   ├── setchannel.py       # Configuração de canais
│   ├── voice_factory.py    # Criação automática de canais de voz
│   ├── welcome.py          # Mensagens de boas-vindas
│
├── utils/
│   ├── __init__.py
│   ├── channels.py         # Leitura e gravação de canais
│   ├── phrase_builder.py   # Frases dinâmicas
│   ├── status_cycle.py     # Ciclo de status
│   ├── welcome.py          # Função de boas-vindas
│
├── config/
│   ├── admin.json          # IDs dos administradores do bot
│   ├── channels.json       # Canais configurados
│   ├── cogs.json           # Controle de cogs carregadas
│   └── .env                # Token e variáveis secretas
│
├── requirements.txt
├── .gitignore
├── LICENSE
└── README.md
```

---

## ⚙️ Instalação

1. Clone o repositório:
   ```bash
   git clone https://github.com/seuusuario/AsyncBOT.git
   cd AsyncBOT
   ```

2. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```

3. Crie o arquivo `.env` dentro da pasta `config/`:
   ```env
   TOKEN=SEU_TOKEN_AQUI
   ```

4. (Opcional) Edite os arquivos JSON de configuração:
   - `admin.json` — IDs dos donos e administradores do bot.

5. Execute o bot:
   ```bash
   python bot.py
   ```

---

## 💬 Comandos Principais

| Comando | Descrição |
|----------|------------|
| `/ping` | Testa a latência do bot |
| `/duelo @alvo` | Inicia um duelo de faroeste |
| `/addadmin @user` | Autoriza um usuário como admin |
| `/rmvadmin @user` | Remove permissão de admin |
| `/load <cog>` | Carrega uma cog |
| `/unload <cog>` | Descarrega uma cog |
| `/reload <cog>` | Recarrega uma cog |
| `/setchannel ...` | Configura canais de texto e voz |

`Os comandos administrativos referem-se excluisivamente a comandos internos do BOT. Não tendo relação com as RULES do servidor.`
`O dono do bot deve ser setado manualmente no arquivo **admin.json** em "bot_owner": [ #ID DO USUARIO DO DISCORD]`

---

## 🚀 Próximas Features
 
zzzzZZzzzZZzZzZ
---


Desenvolvido por **Hatsuk**  

---

## ⚖️ Licença

Distribuído sob a **MIT License** — veja o arquivo [LICENSE](LICENSE) para mais detalhes.
