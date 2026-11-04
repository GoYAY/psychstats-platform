(function (root, factory) {
  var api = factory();
  if (typeof module === 'object' && module.exports) { module.exports = api; }
  else { root.PsychPractice = api; }
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  function escapeHtml(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, function (char) {
      return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char];
    });
  }

  function gradeOption(answer, optionIndex, explanation) {
    return { correct: Number(optionIndex) === Number(answer), answer: Number(answer), explanation: explanation || '' };
  }

  function gradeQuestion(questionId, optionIndex, questions) {
    var question = (questions || []).find(function (item) { return item.id === questionId; });
    if (!question) { throw new Error('Unknown question: ' + questionId); }
    var explanations = question.option_explanations || [];
    return Object.assign(gradeOption(question.answer, optionIndex, explanations[Number(optionIndex)] || question.explanation), {
      termId: question.term_id,
      termLink: 'terms/' + question.term_id + '.html'
    });
  }

  var activeSession = null;

  function createSession(questions, saved) {
    var index = 0, selected = null, firstAnswers = new Map(), score = {correct:0, answered:0};
    function validChoice(question, choice) {
      return question && Number.isInteger(choice) && choice >= 0 && choice < question.options.length;
    }
    if (saved && typeof saved === 'object') {
      var restoredIndex = questions.findIndex(function (question) { return question.id === saved.question_id; });
      if (restoredIndex >= 0) {
        index = restoredIndex;
        selected = validChoice(questions[index], saved.selected) ? saved.selected : null;
        (Array.isArray(saved.first_answers) ? saved.first_answers : []).forEach(function (entry) {
          if (!Array.isArray(entry)) return;
          var question = questions.find(function (item) { return item.id === entry[0]; });
          if (!validChoice(question, entry[1]) || firstAnswers.has(question.id)) return;
          firstAnswers.set(question.id, entry[1]);
          score.answered++;
          if (entry[1] === Number(question.answer)) score.correct++;
        });
      }
    }
    return {
      current:function () { return questions[index % questions.length]; },
      selection:function () { return selected; },
      score:function () { return {correct:score.correct, answered:score.answered}; },
      choose:function (choice) {
        var q = this.current(); choice = Number(choice);
        if (!q || !Number.isInteger(choice) || choice < 0 || choice >= q.options.length) throw Error('Invalid option');
        var result = gradeQuestion(q.id, choice, questions);
        selected = choice;
        if (!firstAnswers.has(q.id)) { score.answered++; if (result.correct) score.correct++; firstAnswers.set(q.id, choice); }
        return result;
      },
      next:function () { index++; selected = null; },
      exportState:function () {
        return {question_id:this.current().id, selected:selected, first_answers:Array.from(firstAnswers.entries())};
      }
    };
  }

  function init(element, ctx) {
    if (!element) { return; }
    function showQuestions(questions) {
      if(ctx&&!ctx.alive())return;
      if (!questions.length) { element.innerHTML = '<p class="empty-state">当前还没有已发布题目。</p>'; return; }
      var resumed = null;
      try {
        var raw = sessionStorage.getItem('psychstats.practice-resume.v1');
        sessionStorage.removeItem('psychstats.practice-resume.v1');
        if (raw) {
          var stored = JSON.parse(raw), age = Date.now() - stored.time;
          if (age >= 0 && age < 1800000) resumed = stored;
        }
      } catch (_) { /* A fresh exercise remains available when storage is blocked. */ }
      var session = createSession(questions, ctx && ctx.state.practice || resumed && resumed.state);
      activeSession = session;
      function show() {
        var q = session.current(), score = session.score();
        element.innerHTML = '<div class="practice-layout"><article class="quiz practice-question"><p class="practice-score">首次作答：' + score.correct + '/' + score.answered + '</p><h2 tabindex="-1">' + escapeHtml(q.question) + '</h2><p class="practice-count">选择后可切换选项，查看各自解释。</p>' + q.options.map(function (option, i) { return '<button class="opt" type="button" data-choice="' + i + '" aria-pressed="false" aria-controls="practice-reading-content" aria-expanded="false"><span aria-hidden="true">' + String.fromCharCode(65+i) + ' · </span>' + escapeHtml(option) + '</button>'; }).join('') + '<div class="explain" role="status" aria-live="polite"></div><div class="practice-controls"><button type="button" data-next-question hidden>下一题 →</button></div></article><aside id="practice-reading-content" class="practice-reading" aria-label="本题考察术语的科普"><div class="practice-reading-placeholder"><p>先试着作答</p><p>选择后在这里查看术语讲解。</p></div></aside></div>';
        var next = element.querySelector('[data-next-question]');
        next.addEventListener('click', function () { session.next(); show(); element.querySelector('h2').focus(); });
        element.querySelectorAll('[data-choice]').forEach(function (button) {
          button.addEventListener('click', function () {
            var result = session.choose(button.getAttribute('data-choice'));
            score = session.score();
            var box = element.querySelector('.explain');
            element.querySelector('.practice-score').textContent = '首次作答：' + score.correct + '/' + score.answered;
            element.querySelectorAll('[data-choice]').forEach(function (choice) {
              choice.classList.remove('correct','wrong');
              choice.setAttribute('aria-pressed', String(choice === button));
              choice.setAttribute('aria-expanded','true');
            });
            button.classList.add(result.correct ? 'correct' : 'wrong');
            box.textContent = (result.correct ? '回答正确。' : '回答错误。') + result.explanation + ' 已显示本题术语讲解。';
            box.classList.add('show');
            next.hidden = false;
            var reading = element.querySelector('.practice-reading');
            if (!reading.dataset.loaded) {
              reading.innerHTML = q.reading_html || '<p>本题考察术语的完整说明：</p><a href="' + escapeHtml(result.termLink) + '">打开术语页 →</a>';
              reading.dataset.loaded = 'true';
            }
          });
        });
      }
      show();
      if (session.selection() !== null) {
        element.querySelector('[data-choice="' + session.selection() + '"]').click();
      }
      if (resumed && Number.isFinite(resumed.scrollY)) {
        window.scrollTo({top:resumed.scrollY, behavior:'instant'});
      }
    }
    var local = typeof window !== 'undefined' && (window.PsychPracticeData || (window.PsychSiteData && window.PsychSiteData.quizzes));
    if (Array.isArray(local)) { showQuestions(local); return function(){activeSession=null;}; }
    if (typeof fetch !== 'function') { element.innerHTML = '<p class="empty-state">题库载入失败，请刷新后重试。</p>'; return; }
    fetch(element.getAttribute('data-quiz-src'),ctx?{signal:ctx.signal}:{}).then(function (response) { return response.json(); }).then(showQuestions).catch(function () { if(ctx&&!ctx.alive())return; element.innerHTML = '<p class="empty-state">题库载入失败，请刷新后重试。</p>'; });
    return function(){activeSession=null;};
  }

  return { gradeOption: gradeOption, gradeQuestion: gradeQuestion, createSession: createSession, init: init,
           captureState:function () { return activeSession && activeSession.exportState(); } };
}));
