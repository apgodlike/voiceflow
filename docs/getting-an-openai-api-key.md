# Getting an OpenAI API key

VoiceFlow uses OpenAI to turn your speech into text, so you need your own OpenAI
API key. You pay OpenAI directly for what you use (transcription is cheap — see
the cost note at the bottom). This takes about 5 minutes.

> Screenshots: replace the `![...]()` placeholders below with your own screenshots
> before publishing the release.

## 1. Create an OpenAI account

Go to **https://platform.openai.com/signup** and sign up (or log in if you already
have an account).

![Sign up screen](images/key-step1-signup.png)

## 2. Add a payment method

A key won't work until billing is set up. Open
**https://platform.openai.com/account/billing** → **Add payment details** and add a
card. You can set a low monthly limit so there are no surprises.

![Billing screen](images/key-step2-billing.png)

## 3. Create the API key

Go to **https://platform.openai.com/api-keys** → **Create new secret key**. Give it
a name like "VoiceFlow" and click create.

![Create key](images/key-step3-create.png)

## 4. Copy the key

The key (starts with `sk-...`) is shown **only once**. Click copy.

> Keep it private — anyone with this key can spend on your account. If it leaks,
> delete it on this page and make a new one.

![Copy key](images/key-step4-copy.png)

## 5. Paste it into VoiceFlow

Open VoiceFlow → it shows a **Settings** window on first run (or right-click the
tray icon → **Settings**). Paste the key into **OpenAI API key** and click **Save**.

![VoiceFlow settings](images/key-step5-voiceflow.png)

That's it — hold **Ctrl + Alt** and start talking.

## What does it cost?

VoiceFlow uses `gpt-4o-mini-transcribe` by default, about **$0.003 per minute** of
audio (~$0.18 per hour of talking). A heavy day of dictation is usually a few cents.
You can switch to the more accurate `gpt-4o-transcribe` (~2× the cost) in Settings.
