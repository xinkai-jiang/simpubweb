const scanButton = document.getElementById('scan-button');
const template = document.getElementById('device-template');
const deviceContainer = document.getElementById('device-container');
const resultContainer = document.getElementById('resultContainer');

scanButton.addEventListener('click', () => {
    fetch('/scan')
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(hostInfo => {
            deviceContainer.innerHTML = '';
            addDevicePanel(hostInfo.server);
            Object.values(hostInfo.clients).forEach(value => {
                addDevicePanel(value);
            });
        })
        .catch(error => {
            resultContainer.innerHTML = `<p style="color: red;">Error: ${error.message}</p>`;
        });
});

function addDevicePanel(hostInfo) {
    const clone = template.content.cloneNode(true);

    clone.querySelector('.device-name').textContent = hostInfo.name;
    clone.querySelector('.device-type').textContent = hostInfo.type;
    clone.querySelector('.device-ip').textContent = hostInfo.ip;

    clone.querySelector('.qr-btn').addEventListener('click', () => {
        alert(`QR Calibration for ${hostInfo.name}`);
    });
    clone.querySelector('.view-btn').addEventListener('click', () => {
        alert(`Get View for ${hostInfo.name}`);
    });

    deviceContainer.appendChild(clone);
}
