import random

partes = {
    "sujeito": [
        "O autômato sentimental",
        "Um corvo filosófico",
        "O servidor em silêncio",
        "A lua testemunha",
        "O código insondável",
        "Você, sim você mesmo",
    ],
    "verbo": [
        "contemplou",
        "questionou",
        "saboreou",
        "seduziu",
        "acariciou",
        "observou atentamente",
        "cantou para",
    ],
    "objeto": [
        "o horizonte nebuloso",
        "um segredo antigo",
        "um café que esfriou",
        "palavras não ditas",
        "os sonhos adormecidos",
        "o caos suave do destino",
    ],
    "adj": [
        "sob a luz tímida da madrugada",
        "com devoção silenciosa",
        "enquanto o mundo não olhava",
        "entre suspiros e gargalhadas",
        "com a elegância de quem sabe mais do que diz",
        "como se fosse arte",
    ]
}

def gerar_frase_status():
    return f"{random.choice(partes['sujeito'])} {random.choice(partes['verbo'])} {random.choice(partes['objeto'])} {random.choice(partes['adj'])}."

import random

def gerar_boas_vindas(nome_membro: str) -> str:
    sujeitos = [
        f"{nome_membro}",
        f"O enigmático {nome_membro}",
        f"O recém-despertado {nome_membro}",
        f"A entidade denominada {nome_membro}",
        f"O viajante abissal {nome_membro}",
    ]

    verbos = [
        "caiu de paraquedas",
        "foi invocado por engano",
        "despertou de um sono de 10.000 anos",
        "sussurrou palavras proibidas no escuro",
        "aceitou um pacto que não lembra ter feito",
        "escutou o chamado além do véu",
        "abriu um grimoire que não devia",
        "olhou para o abismo… e o abismo piscou de volta",
        "recitou *verba arcana* sem permissão",
        "tocou em um artefato amaldiçoado",
    ]

    cthulhianos = [
        "antes que os mares fervam novamente",
        "enquanto o sol se apaga em silêncio",
        "no limiar onde mentes se dissolvem",
        "sob o olhar adormecido de **Cthulhu**",
        "no crepitar dos portões de **R'lyeh**",
        "enquanto sonhos sussurram em línguas mortas",
    ]

    latim = [
        "Memento mori.",
        "Non serviam.",
        "Mundus vult decipi.",
        "Ad astra per aspera.",
        "Igni natura renovatur integra.",
        "Lux in tenebris.",
        "Mortis est dos pretium.",
    ]

    finais = [
        f"{random.choice(cthulhianos)} 👁️",
        f"{random.choice(latim)}",
        "aproveite enquanto ainda há tempo… ⌛",
        "agora não tem mais retorno… 🌑",
        "o caos começa agora 😈",
        "os portões já se abriram… 🌬️",
    ]

    return f"{random.choice(sujeitos)} {random.choice(verbos)}… {random.choice(finais)}"
