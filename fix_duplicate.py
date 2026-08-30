import re
with open("cdss_web/Components/Pages/Predict.razor", "r") as f:
    c = f.read()

# ForceSearchTc is defined twice because I added it to c_sharp_logic but it was already in HEAD.
# Let's remove the one I just added.

c_sharp_logic = """
    private void ForceSearchTc()
    {
        if (string.IsNullOrWhiteSpace(_identity.TcNo)) return;
        _tcError = null;
        _tcSearching = true;
        StateHasChanged();
        _ = SearchPatientAsync(_identity.TcNo);
    }"""

c = c.replace(c_sharp_logic, "")

with open("cdss_web/Components/Pages/Predict.razor", "w") as f:
    f.write(c)
