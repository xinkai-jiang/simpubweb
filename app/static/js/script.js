document.addEventListener("DOMContentLoaded", () => {
    const resultsContainer = document.getElementById("scan-results");

    // 向后端请求扫描结果
    fetch("/scan")
        .then(response => response.json())
        .then(data => {
            // 清空结果容器
            resultsContainer.innerHTML = "";

            data.forEach(result => {
                const li = document.createElement("li");
                li.textContent = `${result.ip} - ${result.message}`;
                li.style.color = result.status === "success" ? "green" : "red";
                resultsContainer.appendChild(li);
            });
        })
        .catch(error => {
            console.error("Error fetching scan results:", error);
            const li = document.createElement("li");
            li.textContent = "Error: Unable to fetch scan results.";
            li.style.color = "red";
            resultsContainer.appendChild(li);
        });
});
