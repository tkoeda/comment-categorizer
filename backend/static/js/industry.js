async function loadIndustries() {
    try {
        const response = await fetch("/industries");
        if (response.ok) {
            const data = await response.json();
            const industryNames = Object.keys(data);

            // List of all industry dropdown IDs.
            const dropdownIDs = [
                "deleteIndustrySelect",
                "updateIndustrySelect",
                "industry_saved",
                "industry_update",
                "industry_combine",
                "industry_clean",
            ];

            dropdownIDs.forEach((id) => {
                const select = document.getElementById(id);
                if (select) {
                    // Clear current options.
                    select.innerHTML = "";
                    // Add a default option.
                    const defaultOption = document.createElement("option");
                    defaultOption.value = "";
                    defaultOption.text = "Select Industry";
                    defaultOption.disabled = true;
                    defaultOption.selected = true;
                    select.appendChild(defaultOption);

                    if (industryNames.length === 0) {
                        const noOption = document.createElement("option");
                        noOption.value = "";
                        noOption.text = "No industries available";
                        noOption.disabled = true;
                        select.appendChild(noOption);
                    } else {
                        industryNames.forEach((industry) => {
                            const option = document.createElement("option");
                            option.value = industry;
                            option.text = industry;
                            select.appendChild(option);
                        });
                    }
                }
            });
        } else {
            console.error("Failed to load industries:", response.statusText);
        }
    } catch (error) {
        console.error("Error loading industries:", error);
    }
}

async function submitAddIndustryForm(event) {
    event.preventDefault();
    const name = document.getElementById("industryName").value;
    const categoriesStr = document.getElementById("industryCategories").value;
    const categories = categoriesStr
        .split(",")
        .map((cat) => cat.trim())
        .filter((cat) => cat !== "");
    try {
        const response = await fetch("/industries", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({ name, categories }),
        });
        const data = await response.json();
        if (response.ok) {
            document.getElementById("addIndustryMessage").innerText =
                "Success: " + data.message;
            document.getElementById("addIndustryForm").reset();
            loadIndustries();
        } else {
            document.getElementById("addIndustryMessage").innerText =
                "Error: " + data.detail;
        }
    } catch (error) {
        console.error("Error adding industry:", error);
        document.getElementById("addIndustryMessage").innerText =
            "Error adding industry.";
    }
}

async function submitDeleteIndustryForm(event) {
    event.preventDefault();
    const deleteSelect = document.getElementById("deleteIndustrySelect");
    const industry = deleteSelect.value;
    try {
        const response = await fetch(
            "/industries/" + encodeURIComponent(industry),
            { method: "DELETE" }
        );
        const data = await response.json();
        if (response.ok) {
            document.getElementById("deleteIndustryMessage").innerText =
                "Success: " + data.message;
            loadIndustries();
        } else {
            document.getElementById("deleteIndustryMessage").innerText =
                "Error: " + data.detail;
        }
    } catch (error) {
        console.error("Error deleting industry:", error);
        document.getElementById("deleteIndustryMessage").innerText =
            "Error deleting industry.";
    }
}

async function submitUpdateIndustryForm(event) {
    event.preventDefault();
    const updateSelect = document.getElementById("updateIndustrySelect");
    const industry = updateSelect.value;
    const categoriesStr = document.getElementById("newCategories").value;
    const categories = categoriesStr
        .split(",")
        .map((cat) => cat.trim())
        .filter((cat) => cat !== "");
    try {
        const response = await fetch(
            "/industries/" + encodeURIComponent(industry) + "/categories",
            {
                method: "PUT",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ categories }),
            }
        );
        const data = await response.json();
        if (response.ok) {
            document.getElementById("updateIndustryMessage").innerText =
                "Success: " + data.message;
            document.getElementById("newCategories").value = "";
            loadIndustries();
        } else {
            document.getElementById("updateIndustryMessage").innerText =
                "Error: " + data.detail;
        }
    } catch (error) {
        console.error("Error updating industry categories:", error);
        document.getElementById("updateIndustryMessage").innerText =
            "Error updating industry categories.";
    }
}
