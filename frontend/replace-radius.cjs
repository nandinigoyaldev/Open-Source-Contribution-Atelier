const fs = require('fs');
const path = require('path');

function walk(dir) {
    let results = [];
    const list = fs.readdirSync(dir);
    list.forEach(function(file) {
        file = dir + '/' + file;
        const stat = fs.statSync(file);
        if (stat && stat.isDirectory()) { 
            results = results.concat(walk(file));
        } else { 
            if (file.endsWith('.tsx') || file.endsWith('.ts')) {
                results.push(file);
            }
        }
    });
    return results;
}

const files = walk('./src');

files.forEach(file => {
    let content = fs.readFileSync(file, 'utf8');
    let original = content;

    // Standardize large radii to rounded-2xl
    content = content.replace(/\brounded-\[2rem\]\b/g, 'rounded-2xl');
    content = content.replace(/\brounded-3xl\b/g, 'rounded-2xl');

    // Standardize medium/button radii to rounded-lg
    // But we have to be careful with things that were explicitly rounded-2xl on buttons.
    // If it has 'bg-primary', 'bg-black', 'border-4', 'px-5 py-4' it's likely a button.
    // To be safe and quick, we'll replace rounded-xl with rounded-lg.
    content = content.replace(/\brounded-xl\b/g, 'rounded-lg');
    
    // Also change some rounded-2xl on obvious button classes (containing hover:-translate-y-1) to rounded-lg
    content = content.replace(/rounded-2xl([^"}]*?hover:-translate-y-1)/g, 'rounded-lg$1');

    if (content !== original) {
        fs.writeFileSync(file, content, 'utf8');
        console.log(`Updated ${file}`);
    }
});
