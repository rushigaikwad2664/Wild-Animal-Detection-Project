ADVICE_DATA = {
    "elephant": [
        "Maintain at least 50 meters distance",
        "Do not make loud noises",
        "Inform forest authorities immediately",
        "Avoid direct confrontation",
    ],
    "bear": [
        "Stay calm and do not run",
        "Avoid eye contact",
        "Back away slowly",
        "Alert nearby people",
    ],
    "zebra": ["Keep safe distance", "Do not attempt to touch", "Monitor movement carefully"],
    "giraffe": ["Maintain distance", "Avoid sudden movements", "Ensure no crowd gathering"],
    "leopard": [
        "Stay indoors and keep children and pets inside",
        "Do not run or turn your back",
        "Call forest department immediately",
    ],
    "tiger": ["Stay indoors", "Do not approach or run", "Call forest department immediately"],
    "lion": ["Stay indoors", "Do not approach or run", "Call forest department immediately"],
    "deer": ["Keep distance", "Do not feed", "Keep dogs away"],
    "monkey": ["Keep food covered", "Do not make eye contact or feed", "Move away calmly"],
    "crocodile": ["Stay away from water", "Keep children and pets back", "Alert authorities"],
    "snake": ["Do not touch it", "Step back slowly", "Call a snake rescue / forest helpline"],
}


def get_advice(animal):
    return ADVICE_DATA.get(str(animal).lower(), ["No advice available"])
