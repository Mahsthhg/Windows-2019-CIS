let current = 0, correct = 0, wrong = 0, answered = 0, startTime = null, timerInterval = null;
const startBtn = document.getElementById('startBtn');
const nextBtn = document.getElementById('nextBtn');
const skipBtn = document.getElementById('skipBtn');
const qBox = document.getElementById('question-box');

function showQuestion() {
  if (current >= questions.length) {
    finishQuiz();
    return;
  }

  nextBtn.classList.add("hidden");
  const q = questions[current];

  const options = [...q.options];
  const correctOption = q.correct;
  options.splice(options.indexOf(correctOption), 1);
  const shuffledOptions = [...options].sort(() => Math.random() - 0.5);
  const finalOptions = [];
  let inserted = false;
  shuffledOptions.forEach(opt => {
    finalOptions.push(opt);
    if (Math.random() < 0.7 && !inserted) {
      finalOptions.push(correctOption);
      inserted = true;
    }
  });
  if (!inserted) finalOptions.push(correctOption);
  if (!finalOptions.includes(correctOption)) {
    finalOptions[Math.floor(Math.random() * finalOptions.length)] = correctOption;
  }

  qBox.innerHTML = `<h3>${current + 1}. ${q.q}</h3>` +
    finalOptions.map(o => `<div class='option' onclick='checkAnswer(this,"${o.replace(/"/g, '&quot;')}","${correctOption.replace(/"/g, '&quot;')}")'>${o}</div>`).join("");
}

function checkAnswer(selectedOptionElement, selectedAnswer, correctAnswer) {
  document.querySelectorAll(".option").forEach(o => o.style.pointerEvents = "none");
  answered++;

  if (selectedAnswer === correctAnswer) {
    correct++;
    selectedOptionElement.style.backgroundColor = "#4CAF50";
    selectedOptionElement.style.color = "white";
    addStars(20);
    qBox.insertAdjacentHTML("beforeend", "<p style='color:lightgreen;font-weight:bold; margin-top: 10px;'>آفرین! درست جواب دادی 🌟</p>");
  } else {
    wrong++;
    selectedOptionElement.style.backgroundColor = "#f44336";
    selectedOptionElement.style.color = "white";
    document.querySelectorAll(".option").forEach(opt => {
      if (opt.textContent.trim() === correctAnswer) {
        opt.style.backgroundColor = "#4CAF50";
        opt.style.color = "white";
      }
    });
    qBox.insertAdjacentHTML("beforeend", `<p style='color:#ff6868;font-weight:bold; margin-top: 10px;'>اشتباه پاسخ دادی ❌<br>پاسخ درست: ${correctAnswer}</p>`);
  }

  updateScoreboard();
  nextBtn.classList.remove("hidden");
}

function updateScoreboard() {
  document.getElementById("correctCount").innerText = correct;
  document.getElementById("wrongCount").innerText = wrong;
  document.getElementById("score").innerText = correct * 5;
}

function updateTimer() {
  const t = Math.floor((Date.now() - startTime) / 1000);
  document.getElementById("timer").innerText = t;
}

function addStars(n) {
  for (let i = 0; i < n; i++) {
    const s = document.createElement("div");
    s.className = "star";
    s.style.left = Math.random() * 100 + "vw";
    s.style.top = "0";
    document.body.appendChild(s);
    setTimeout(() => s.remove(), 1000);
  }
}

nextBtn.onclick = () => {
  current++;
  showQuestion();
};

skipBtn.onclick = () => {
  finishQuiz();
};

function finishQuiz() {
  clearInterval(timerInterval);
  document.getElementById("quiz-page").classList.remove("active");
  const resPage = document.getElementById("result-page");
  resPage.classList.add("active");

  const timeSpent = Math.floor((Date.now() - startTime) / 1000);
  const totalAnswered = correct + wrong;
  const skipped = questions.length - totalAnswered;
  const finalScore = correct * 5;
  const percent = totalAnswered > 0 ? Math.round((correct / totalAnswered) * 100) : 0;

  let grade = "";
  if (percent >= 90) grade = "عالی 🏆";
  else if (percent >= 75) grade = "خوب 👍";
  else if (percent >= 50) grade = "متوسط 📚";
  else grade = "نیاز به تلاش بیشتر 💪";

  document.getElementById("resultText").innerHTML = `
    <p>👏 آزمون پایان یافت!</p>
    <p><span class="result-label">دانش‌آموز:</span> <span class="result-value">${document.getElementById('studentName').value || 'نام شما'}</span></p>
    <hr style="border-color:rgba(255,255,255,0.3); margin:0.8rem 0;">
    <p><span class="result-label">تعداد کل سؤالات:</span> <span class="result-value">${questions.length}</span></p>
    <p><span class="result-label">پاسخ‌های داده شده:</span> <span class="result-value">${totalAnswered}</span></p>
    <p><span class="result-label">پاسخ‌های درست:</span> <span class="result-value" style="color:#7cfc00;">${correct}</span></p>
    <p><span class="result-label">پاسخ‌های غلط:</span> <span class="result-value" style="color:#ff6868;">${wrong}</span></p>
    <p><span class="result-label">سؤالات رد شده:</span> <span class="result-value">${skipped}</span></p>
    <hr style="border-color:rgba(255,255,255,0.3); margin:0.8rem 0;">
    <p><span class="result-label">امتیاز نهایی:</span> <span class="result-value" style="font-size:1.6rem; color:#ffe66d;">${finalScore}</span></p>
    <p><span class="result-label">درصد موفقیت:</span> <span class="result-value">${percent}%</span></p>
    <p><span class="result-label">ارزیابی:</span> <span class="result-value">${grade}</span></p>
    <p><span class="result-label">زمان پاسخ‌دهی:</span> <span class="result-value">${timeSpent} ثانیه</span></p>
  `;
}

startBtn.onclick = () => {
  const studentNameInput = document.getElementById('studentName');
  if (!studentNameInput.value.trim()) {
    alert("لطفاً نام و نام خانوادگی خود را وارد کنید.");
    return;
  }
  document.getElementById("start-page").classList.remove("active");
  document.getElementById("quiz-page").classList.add("active");
  startTime = Date.now();
  timerInterval = setInterval(updateTimer, 1000);
  showQuestion();
};
