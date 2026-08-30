with open("llm/explainer.py", "r") as f:
    content = f.read()

import re

# Update System Prompt
old_system_prompt_match = re.search(r'SYSTEM_PROMPT = """(.*?)"""', content, re.DOTALL)
if old_system_prompt_match:
    new_system_prompt = """Sen uzman bir dermatolog gibi davranan klinik bir asistansın.
Sana bir psoriazis hastası için belirlenen sevk kararları ve bu kararların altındaki tıbbi bulgular verilecek.

Görevin: Bu yönlendirme kararlarını bir hekimin dosya notuna (epikriz / konsültasyon notu) yazabileceği ciddiyette, kısalıkta ve doğallıkta özetlemektir.

ZORUNLU KURALLAR:
1. KESİNLİKLE "Yazılımsal" veya "Yapay Zeka" ağzıyla konuşma! "Model", "Sistem", "Algoritma", "Güven skoru", "Parametre", "Karar aleyhine etki", "Negatif/Pozitif faktör" gibi kelimeleri ASLA KULLANMA.
2. "Klinik karar destek sistemi şu kararı verdi" gibi robotik girişler YAPMA. Doğrudan tıbbi duruma gir (Örn: "Hastanın mevcut klinik tablosunda...").
3. Metin, kıdemli bir uzman doktorun hasta dosyasına düştüğü tıbbi bir not gibi akıcı, doğal ve doğrudan olmalıdır. Edebi veya süslü cümleler kurma.
4. Kesinlikle hastalık tanısı uydurma veya spesifik bir ilaç ismi (örn: Methotrexate) önerme. Sadece verilen sevk kararlarının "tıbbi nedenlerini" açıkla.
5. Sana verilen % güven oranlarını veya istatistiksel ifadeleri metne YAZMA. Bunun yerine "kuvvetle endikedir", "uygun görülmektedir", "ön planda düşünülmektedir" gibi klinik ifadeler kullan.

KÖTÜ ÖRNEK (Yazılımsal): "Sistem %87 güven oranıyla FTR önermektedir. Kararı destekleyen en güçlü parametre tırnak tutulumudur."
İYİ ÖRNEK (Klinik): "Hastada izlenen tırnak tutulumu ve 30 dakikayı aşan sabah tutukluğu psöriyatik artrit açısından yüksek risk taşıdığından FTR konsültasyonu endikedir."
"""
    content = content.replace(old_system_prompt_match.group(1), new_system_prompt)

# Update User Prompt Generation (build_explanation_prompt)
content = content.replace('f"\\n{LABEL_DISPLAY_NAMES[label]} (güven: %{prob * 100:.0f}):"', 'f"\\nÖNERİ: {LABEL_DISPLAY_NAMES[label]}\\nKLİNİK GEREKÇELER:"')
content = content.replace('prompt_lines.append(f"  - {f[\'ozellik\']}: {f[\'etki\']}")', 'prompt_lines.append(f"  - {f[\'ozellik\']}")')
content = content.replace('f"\\n{LABEL_DISPLAY_NAMES[label]} önerilmedi (güven: %{guven:.0f})."', 'f"\\n{LABEL_DISPLAY_NAMES[label]} konsültasyonu şu aşamada öncelikli görülmemiştir."')
content = content.replace('"Hasta verileri analiz edildi. Aşağıdaki klinik karar önerisi üretildi:\\n",', '"Hastanın mevcut klinik verileri doğrultusunda aşağıdaki yönlendirme kararları alınmıştır:\\n",')

with open("llm/explainer.py", "w") as f:
    f.write(content)
print("Prompt updated.")
