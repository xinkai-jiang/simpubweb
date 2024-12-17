document.addEventListener('DOMContentLoaded', () => {
    const scanButton = document.getElementById('scan-button');
    const xrTemplate = document.getElementById('xr-template');
    const masterTemplate = document.getElementById('master-template');
    const deviceContainer = document.getElementById('device-container');
    const resultContainer = document.getElementById('resultContainer');

    // Handle "Scan" button click
    scanButton.addEventListener('click', () => {
        fetch('/scan')
            .then(response => {
                if (!response.ok) {
                    throw new Error('Failed to scan devices');
                }
                return response.json();
            })
            .then(responseData => {
                if (responseData.status !== "success") {
                    throw new Error(responseData.message);
                }
                deviceContainer.innerHTML = ''; // Clear existing devices
                addMasterNode(responseData.master); // Add master node
                if (responseData.nodes) {
                    Object.values(responseData.nodes).forEach(node => addNodePanel(node));
                }
            })
            .catch(error => {
                resultContainer.innerHTML = `<p style="color: red;">Error: ${error.message}</p>`;
            });
    });

    // Function to add the master node
    function addMasterNode(masterInfo) {
        const clone = masterTemplate.content.cloneNode(true);

        // Set master attributes
        const deviceHeader = clone.querySelector('.device-header');
        deviceHeader.setAttribute('data-name', masterInfo.name);
        deviceHeader.setAttribute('data-node-id', masterInfo.nodeID);
        deviceHeader.setAttribute('data-ip', masterInfo.addr.ip);
        deviceHeader.setAttribute('data-service-port', masterInfo.servicePort);

        // Set visible details
        clone.querySelector('.device-name').textContent = masterInfo.name;
        clone.querySelector('.device-type').textContent = `Type: Master`;
        clone.querySelector('.device-ip').textContent = `IP: ${masterInfo.addr.ip}`;

        // Append the master node panel to the container
        deviceContainer.appendChild(clone);
    }

    // Function to create and add a regular node panel to the DOM
    function addNodePanel(nodeInfo) {
        const clone = xrTemplate.content.cloneNode(true);

        // Set node attributes
        const deviceHeader = clone.querySelector('.device-header');
        deviceHeader.setAttribute('data-name', nodeInfo.name);
        deviceHeader.setAttribute('data-node-id', nodeInfo.nodeID);
        deviceHeader.setAttribute('data-ip', nodeInfo.addr.ip);
        deviceHeader.setAttribute('data-service-port', nodeInfo.servicePort);

        // Set visible details
        clone.querySelector('.device-name').textContent = nodeInfo.name;
        clone.querySelector('.device-type').textContent = `Type: ${nodeInfo.type}`;
        clone.querySelector('.device-ip').textContent = `IP: ${nodeInfo.addr.ip}`;

        // Add event listeners to buttons
        addButtonEventListeners(clone, deviceHeader);

        // Append the node panel to the container
        deviceContainer.appendChild(clone);
    }

    // Function to add event listeners to the buttons
    function addButtonEventListeners(clone, deviceHeader) {
        const name = deviceHeader.getAttribute('data-name');
        const ip = deviceHeader.getAttribute('data-ip');
        const servicePort = deviceHeader.getAttribute('data-service-port');

        // Start QR Alignment button
        clone.querySelector('.start-btn').addEventListener('click', () => {
            sendPostRequest('/start-qr-alignment', { "name": name, "ip": ip, servicePort: servicePort }, 'Start QR Alignment');
        });

        // Stop QR Alignment button
        clone.querySelector('.stop-btn').addEventListener('click', () => {
            sendPostRequest('/stop-qr-alignment', { "name": name, "ip": ip, servicePort: servicePort }, 'Stop QR Alignment');
        });

        // Rename button
        clone.querySelector('.rename-btn').addEventListener('click', () => {
            const newName = prompt('Enter new name for the device:');
            if (newName) {
                alert(`Device renamed to: ${newName}`);
            }
        });

        // View Capture button
        clone.querySelector('.view-btn').addEventListener('click', () => {
            alert(`Viewing capture for Node: ${deviceHeader.getAttribute('data-node-id')}`);
        });
    }

    // Function to send a POST request and handle the response
    function sendPostRequest(url, body, actionName) {
        fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(body),
        })
            .then(response => response.json())
            .then(data => {
                alert(`${actionName}: ${data.message}`);
            })
            .catch(error => {
                console.error(`${actionName} Error:`, error);
                alert(`${actionName} failed.`);
            });
    }
});
