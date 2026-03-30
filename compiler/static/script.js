// Fetch UI Elements
const runBtn = document.querySelector('.run-btn');
const submitBtn = document.querySelector('.submit-btn');
const switchBtn = document.querySelector('.switch-btn');
const consoleBox = document.querySelector('.console-box');

// 1. Run Button Logic
runBtn.addEventListener('click', () => {
    // Get the current code from Monaco Editor
    const code = editor.getValue();
    console.log("Running Code:", code);
    
    // Placeholder UI update
    consoleBox.innerHTML = '<span style="color: #60a5fa;">Running...</span>';
    
    // Simulate backend execution delay
    setTimeout(() => {
        consoleBox.innerHTML = 'Execution finished. (Backend connection pending)';
    }, 1000);
});

// 2. Submit Button Logic
submitBtn.addEventListener('click', () => {
    const code = editor.getValue();
    console.log("Submitting Code:", code);
    
    // Placeholder UI update
    const confirmSubmit = confirm("Are you sure you want to lock and submit Part A?");
    if(confirmSubmit) {
        editor.updateOptions({ readOnly: true });
        consoleBox.innerHTML = '<span style="color: #16a34a;">Code Submitted Successfully! (Waiting for swap)</span>';
        
    }
});

// 3. Switch Code Button Logic
switchBtn.addEventListener('click', () => {
    console.log("Switching Code...");
    
    consoleBox.innerHTML = '<span style="color: #fbbf24;">Switching to Part B...</span>';
    
    setTimeout(() => {
        

        // 🔁 Reset time
        timeRemaining = 180;

        editor.updateOptions({ readOnly: false });
        editor.setValue("// Partner's Part A...\n\n// Continue Part B here:\n");
        document.getElementById('phaseLabel').innerText = "Part B";
        document.getElementById('partBadge').innerText = "PART B";
        consoleBox.innerHTML = 'Ready to code Part B.';

        // ▶️ Start new timer
        startTimer();

        // Existing logic
        
    }, 1500);
});

// 4. Timer Logic
const timerElement = document.getElementById('timer');
let timeRemaining = 180; // 3 minutes (180 seconds)
let timerInterval = null;
function formatTime(seconds) {
    const m = Math.floor(seconds / 60).toString().padStart(2, '0');
    const s = (seconds % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
}

// Start immediately on script load
function startTimer() {
    clearInterval(timerInterval);   // stop old timer

    timerInterval = setInterval(() => {
        if (timeRemaining <= 0) {
            clearInterval(timerInterval);
            timerElement.innerText = "00:00";

            if (typeof editor !== 'undefined') {
                editor.updateOptions({ readOnly: true });
                consoleBox.innerHTML = '<span style="color: #ef4444;">Time is up! Code locked.</span>';
            }
        } else {
            timerElement.innerText = formatTime(timeRemaining);
            timeRemaining--;
        }
    }, 1000);
}
window.onload = () => {
    timeRemaining = 180;
    startTimer();
};
