function loadImage(src) {
    return new Promise((resolve) => {
        const img = new Image();
        img.crossOrigin = 'Anonymous';
        img.onload = () => resolve(img);
        img.onerror = () => resolve(null);
        img.src = src;
    });
}

async function buildCertificateCanvas(childName, branchName, ticketNumber) {
    const canvas = document.createElement('canvas');
    canvas.width = 1600;
    canvas.height = 1131; // A4 aspect ratio in pixels
    const ctx = canvas.getContext('2d');

    // Background gradient
    const bgGrad = ctx.createLinearGradient(0, 0, 1600, 1131);
    bgGrad.addColorStop(0, '#0a1128');
    bgGrad.addColorStop(0.5, '#001f54');
    bgGrad.addColorStop(1, '#034078');
    ctx.fillStyle = bgGrad;
    ctx.fillRect(0, 0, 1600, 1131);

    // Decorative Borders
    ctx.strokeStyle = '#00f2fe';
    ctx.lineWidth = 10;
    ctx.strokeRect(40, 40, 1520, 1051);

    ctx.strokeStyle = 'rgba(255, 255, 255, 0.2)';
    ctx.lineWidth = 2;
    ctx.strokeRect(55, 55, 1490, 1021);

    // Corner Ornaments
    ctx.fillStyle = '#00f2fe';
    ctx.fillRect(30, 30, 30, 30);
    ctx.fillRect(1540, 30, 30, 30);
    ctx.fillRect(30, 1071, 30, 30);
    ctx.fillRect(1540, 1071, 30, 30);

    // Load and render ITSTEP Logo
    const logoImg = await loadImage('assets/logo.jpg');
    if (logoImg) {
        const logoWidth = 110;
        const logoHeight = 110;
        const logoX = 800 - logoWidth / 2;
        const logoY = 75;
        const r = 16;

        ctx.save();
        ctx.beginPath();
        ctx.moveTo(logoX + r, logoY);
        ctx.arcTo(logoX + logoWidth, logoY, logoX + logoWidth, logoY + logoHeight, r);
        ctx.arcTo(logoX + logoWidth, logoY + logoHeight, logoX, logoY + logoHeight, r);
        ctx.arcTo(logoX, logoY + logoHeight, logoX, logoY, r);
        ctx.arcTo(logoX, logoY, logoX + logoWidth, logoY, r);
        ctx.closePath();
        ctx.clip();
        ctx.drawImage(logoImg, logoX, logoY, logoWidth, logoHeight);
        ctx.restore();

        // Glowing border around logo
        ctx.save();
        ctx.beginPath();
        ctx.moveTo(logoX + r, logoY);
        ctx.arcTo(logoX + logoWidth, logoY, logoX + logoWidth, logoY + logoHeight, r);
        ctx.arcTo(logoX + logoWidth, logoY + logoHeight, logoX, logoY + logoHeight, r);
        ctx.arcTo(logoX, logoY + logoHeight, logoX, logoY, r);
        ctx.arcTo(logoX, logoY, logoX + logoWidth, logoY, r);
        ctx.closePath();
        ctx.strokeStyle = '#00f2fe';
        ctx.lineWidth = 3;
        ctx.stroke();
        ctx.restore();
    }

    // Academy Title Header
    ctx.font = 'bold 36px "Inter", sans-serif';
    ctx.fillStyle = '#00f2fe';
    ctx.textAlign = 'center';
    ctx.fillText('АКАДЕМІЯ ITSTEP', 800, 225);

    ctx.font = '500 24px "Inter", sans-serif';
    ctx.fillStyle = '#a0aec0';
    ctx.fillText(branchName || 'Філія ITSTEP', 800, 265);

    // Certificate Main Title
    ctx.font = '900 64px "Inter", sans-serif';
    ctx.fillStyle = '#ffffff';
    ctx.fillText('СЕРТИФІКАТ', 800, 360);

    ctx.font = '500 26px "Inter", sans-serif';
    ctx.fillStyle = '#cbd5e0';
    ctx.fillText('Цей сертифікат засвідчує, що', 800, 425);

    // Child Name Highlighted
    ctx.font = 'bold 56px "Inter", sans-serif';
    const nameGrad = ctx.createLinearGradient(400, 0, 1200, 0);
    nameGrad.addColorStop(0, '#00f2fe');
    nameGrad.addColorStop(1, '#4facfe');
    ctx.fillStyle = nameGrad;
    ctx.fillText(childName || 'Учасник Квізу', 800, 505);

    // Line under name
    ctx.beginPath();
    ctx.moveTo(500, 530);
    ctx.lineTo(1100, 530);
    ctx.strokeStyle = '#00f2fe';
    ctx.lineWidth = 3;
    ctx.stroke();

    // Achievement text
    ctx.font = '500 28px "Inter", sans-serif';
    ctx.fillStyle = '#ffffff';
    ctx.fillText('успішно пройшов(ла) інтерактивний IT-квіст', 800, 595);

    ctx.font = 'bold 38px "Inter", sans-serif';
    ctx.fillStyle = '#ffb703';
    ctx.fillText('«Мої літні канікули — це баг чи фіча?»', 800, 655);

    ctx.font = '500 24px "Inter", sans-serif';
    ctx.fillStyle = '#cbd5e0';
    ctx.fillText('та отримав(ла) офіційне підтвердження високого IT-потенціалу!', 800, 710);

    // Raffle Ticket Info
    ctx.fillStyle = 'rgba(255, 255, 255, 0.05)';
    if (ctx.roundRect) {
        ctx.beginPath();
        ctx.roundRect(450, 760, 700, 110, 15);
        ctx.fill();
    } else {
        ctx.fillRect(450, 760, 700, 110);
    }
    ctx.strokeStyle = '#ffb703';
    ctx.lineWidth = 2;
    ctx.stroke();

    ctx.font = 'bold 22px "Inter", sans-serif';
    ctx.fillStyle = '#ffb703';
    ctx.fillText('УНІКАЛЬНИЙ НОМЕР УЧАСНИКА РОЗІГРАШУ ПРИЗІВ:', 800, 800);

    ctx.font = 'bold 36px "Courier New", monospace';
    ctx.fillStyle = '#ffffff';
    ctx.fillText(ticketNumber || 'ITS-000000', 800, 845);

    // Footer info
    const today = new Date().toLocaleDateString('uk-UA', { year: 'numeric', month: 'long', day: 'numeric' });
    ctx.font = '500 20px "Inter", sans-serif';
    ctx.fillStyle = '#a0aec0';
    ctx.textAlign = 'left';
    ctx.fillText(`Дата видачі: ${today}`, 120, 990);

    ctx.textAlign = 'right';
    ctx.fillText('Академія ITSTEP © 2026', 1480, 990);

    return canvas;
}

async function getCertificateBase64(childName, branchName, ticketNumber) {
    const canvas = await buildCertificateCanvas(childName, branchName, ticketNumber);
    const dataUrl = canvas.toDataURL('image/png');
    return dataUrl.split(',')[1] || dataUrl;
}

async function generateCertificate(childName, branchName, ticketNumber) {
    const canvas = await buildCertificateCanvas(childName, branchName, ticketNumber);
    const link = document.createElement('a');
    link.download = `Certificate_${(childName || 'Participant').replace(/\s+/g, '_')}_ITSTEP.png`;
    link.href = canvas.toDataURL('image/png');
    link.click();
}
