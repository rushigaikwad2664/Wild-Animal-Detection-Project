FALLBACK_REPLY = "🤖 Ask about animals like tiger, elephant, lion, bear etc."

ANIMAL_INFO = {
    "elephant": "🐘 Elephant: Large herbivore. Stay away, avoid noise, never block its path.",
    "bear": "🐻 Bear: Dangerous if threatened. Stay calm, avoid eye contact, slowly back away.",
    "zebra": "🦓 Zebra: Generally harmless but unpredictable. Maintain distance.",
    "giraffe": "🦒 Giraffe: Avoid close contact. Can kick dangerously.",
    "leopard": "🐆 Leopard: Very dangerous. Stay indoors, keep children and pets inside, alert forest officials.",
    "tiger": "🐅 Tiger: Extremely dangerous. Stay indoors and inform authorities immediately.",
    "lion": "🦁 Lion: Stay inside, do not run, alert forest officials.",
    "deer": "🦌 Deer: Usually harmless but can bolt or kick. Keep distance and do not feed.",
    "monkey": "🐒 Monkey: Can snatch food and bite. Do not feed or stare; keep food covered.",
    "crocodile": "🐊 Crocodile: Very dangerous. Stay far from water edges and alert authorities.",
    "snake": "🐍 Snake: Do not touch or corner it. Move away slowly and call a snake rescuer.",
    "boar": "🐗 Wild Boar: Can attack suddenly. Maintain distance and avoid provoking.",
    "cow": "🐄 Cow: Usually safe but can charge if scared.",
    "horse": "🐎 Horse: Avoid sudden movement behind it.",
    "dog": "🐕 Dog: If aggressive, avoid eye contact and move slowly.",
    "cat": "🐈 Cat: Generally harmless.",
    "bird": "🐦 Bird: No threat.",
}


def get_chat_response(message):
    message = (message or "").lower()
    for animal, info in ANIMAL_INFO.items():
        if animal in message:
            return info
    return FALLBACK_REPLY
