import re
with open("cdss_web/Components/Pages/Predict.razor", "r") as f:
    c = f.read()

# Replace the Tarih line
c = re.sub(r'Tarih: @\(DateTime\.TryParse\(pr\.Timestamp, out var dt\) \? dt\.ToString\("dd\.MM\.yyyy HH:mm"\) : pr\.Timestamp\)\s*&nbsp;·&nbsp;', '', c)

with open("cdss_web/Components/Pages/Predict.razor", "w") as f:
    f.write(c)
