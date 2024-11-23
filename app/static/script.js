// 获取 "Scan" 按钮和结果容器
const scanButton = document.getElementById('scan-button');
const template = document.getElementById('device-template');
const deviceContainer = document.getElementById('device-container');
const resultContainer = document.getElementById('resultContainer');

// 为按钮添加点击事件监听器
scanButton.addEventListener('click', () => {
    // 向 /scan 路由发送 GET 请求
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
            // 错误处理
            resultContainer.innerHTML = `<p style="color: red;">Error: ${error.message}</p>`;
        });
});

function addDevicePanel(hostInfo) {
    // 克隆模板内容
    const clone = template.content.cloneNode(true);

    // 修改克隆的内容
    clone.querySelector('.device-name').textContent = hostInfo.name;
    clone.querySelector('.device-type').textContent = hostInfo.type;
    clone.querySelector('.device-ip').textContent = hostInfo.ip;

    // 为按钮添加事件监听器
    clone.querySelector('.qr-btn').addEventListener('click', () => {
        alert(`QR Calibration for ${hostInfo.name}`);
    });
    clone.querySelector('.view-btn').addEventListener('click', () => {
        alert(`Get View for ${hostInfo.name}`);
    });

    // 将克隆的模板内容添加到容器
    deviceContainer.appendChild(clone);
}
