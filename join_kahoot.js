// Simple Kahoot joiner using kahoot.js-latest / kahoot.js-updated / kahoot.js
const pin = process.argv[2];
let name = process.argv[3] || null;

const colors = {
    reset: '\x1b[0m',
    red: '\x1b[31m',
    green: '\x1b[32m',
    yellow: '\x1b[33m',
    cyan: '\x1b[36m',
    magenta: '\x1b[35m'
};

function style(text, color) {
    return `${color}${text}${colors.reset}`;
}

function info(message) {
    console.log(style('[INFO]', colors.cyan), message);
}

function success(message) {
    console.log(style('[OK]', colors.green), message);
}

function warn(message) {
    console.log(style('[WARN]', colors.yellow), message);
}

function error(message) {
    console.error(style('[ERROR]', colors.red), message);
}

function event(message) {
    console.log(style('[EVENT]', colors.magenta), message);
}

if (!pin) {
    error('Usage: node join_kahoot.js <PIN> [nickname]');
    process.exit(1);
}

process.on('uncaughtException', err => {
    error('Uncaught exception: ' + (err && err.stack ? err.stack : err));
    process.exit(1);
});

process.on('unhandledRejection', reason => {
    error('Unhandled promise rejection: ' + reason);
    process.exit(1);
});

try {
    let Kahoot;
    try {
        Kahoot = require('kahoot.js-latest');
        success('Loaded kahoot.js-latest');
    } catch (firstErr) {
        try {
            Kahoot = require('kahoot.js-updated');
            success('Loaded kahoot.js-updated');
        } catch (secondErr) {
            try {
                Kahoot = require('kahoot.js');
                success('Loaded kahoot.js');
            } catch (thirdErr) {
                error('Failed to load kahoot.js-latest, kahoot.js-updated, and kahoot.js.');
                error(firstErr.message);
                error(secondErr.message);
                error(thirdErr.message);
                throw thirdErr;
            }
        }
    }

    const client = new Kahoot();
    client.on('error', err => {
        error('Client error: ' + (err && err.stack ? err.stack : err));
        process.exit(1);
    });

    if (!name) {
        name = 'Bot' + Math.random().toString(36).substring(2, 8);
    }

    info(`Joining PIN ${pin} as ${name} ...`);

    client.join(pin, name, [name + '_team']).then(() => {
        success('Joined successfully. Waiting for events...');
    }).catch(err => {
        error('Failed to join: ' + (err && err.message ? err.message : err));
        process.exit(2);
    });

    function formatJoinInfo(info) {
        const parts = [];
        if (info.gameType) parts.push(`type=${info.gameType}`);
        if (info.liveGameId) parts.push(`liveGameId=${info.liveGameId}`);
        if (info.startTime) parts.push(`startTime=${new Date(info.startTime).toISOString()}`);
        if (typeof info.loginRequired === 'boolean') parts.push(`loginRequired=${info.loginRequired}`);
        if (typeof info.isAnonymous === 'boolean') parts.push(`anonymous=${info.isAnonymous}`);
        return parts.length ? parts.join(', ') : JSON.stringify(info);
    }

    function normalizeQuestionPayload(q) {
        if (!q || typeof q !== 'object') return q;
        if (q.nextGameBlockData && typeof q.nextGameBlockData === 'object') {
            return normalizeQuestionPayload(q.nextGameBlockData);
        }
        if (q.quizQuestion && typeof q.quizQuestion === 'object') {
            return normalizeQuestionPayload(q.quizQuestion);
        }
        if (q.question && typeof q.question === 'object') {
            return normalizeQuestionPayload(q.question);
        }
        if (q.firstGameBlockData && typeof q.firstGameBlockData === 'object') {
            return normalizeQuestionPayload(q.firstGameBlockData);
        }
        return q;
    }

    function findStringField(value, seen = new Set()) {
        if (value == null) return null;
        if (typeof value === 'string' || typeof value === 'number') return String(value);
        if (seen.has(value)) return null;
        seen.add(value);

        if (Array.isArray(value)) {
            for (const item of value) {
                const result = findStringField(item, seen);
                if (result) return result;
            }
            return null;
        }

        const priorityKeys = ['question', 'prompt', 'title', 'description', 'content', 'text', 'questionText', 'label', 'answer', 'choice', 'message', 'titlePlain'];
        for (const key of priorityKeys) {
            if (key in value) {
                const result = findStringField(value[key], seen);
                if (result) return result;
            }
        }

        for (const key of Object.keys(value)) {
            if (['id', 'type', 'url', 'src', 'thumbnail', 'startTime', 'endTime', 'width', 'height', 'correct', 'pointsMultiplier', 'questionFormat', 'layout', 'backgroundColor', 'reactions', 'languageInfo', 'externalRef', 'resources', 'service', 'fullUrl', 'quizQuestion', 'firstGameBlockData', 'nextGameBlockData'].includes(key)) {
                continue;
            }
            const result = findStringField(value[key], seen);
            if (result) return result;
        }

        return null;
    }

    function getText(value) {
        if (value == null) return null;
        if (typeof value === 'string') return value;
        if (typeof value === 'number') return String(value);
        if (typeof value === 'object') {
            if (value.text) return getText(value.text);
            if (value.question) return getText(value.question);
            if (value.prompt) return getText(value.prompt);
            if (value.title) return getText(value.title);
            if (value.description) return getText(value.description);
            if (value.content) return getText(value.content);
            if (value.answer) return getText(value.answer);
            if (value.choice) return getText(value.choice);
            return findStringField(value);
        }
        return null;
    }

    function getImageUrls(payload) {
        const urls = new Set();

        function add(item) {
            if (!item) return;
            if (typeof item === 'string') {
                if (item.startsWith('http')) urls.add(item);
                return;
            }
            if (item.url && typeof item.url === 'string') urls.add(item.url);
            if (item.src && typeof item.src === 'string') urls.add(item.src);
            if (item.imageUrl && typeof item.imageUrl === 'string') urls.add(item.imageUrl);
            if (item.thumbnail && typeof item.thumbnail === 'string') urls.add(item.thumbnail);
            if (item.image && typeof item.image === 'string') urls.add(item.image);
            if (Array.isArray(item.image)) item.image.forEach(add);
            if (Array.isArray(item.images)) item.images.forEach(add);
            if (Array.isArray(item.media)) item.media.forEach(add);
            if (item.imageMetadata && item.imageMetadata.id) {
                urls.add(`https://media.kahoot.it/${item.imageMetadata.id}`);
            }
            if (item.nextGameBlockData) add(item.nextGameBlockData);
            if (item.quizQuestion) add(item.quizQuestion);
            if (item.question) add(item.question);
            if (item.firstGameBlockData) add(item.firstGameBlockData);
        }

        if (Array.isArray(payload)) {
            payload.forEach(add);
        } else {
            add(payload);
        }

        return Array.from(urls);
    }

    function getQuestionIndex(q) {
        if (q == null || typeof q !== 'object') return null;
        if (typeof q.questionIndex === 'number') return q.questionIndex + 1;
        if (typeof q.index === 'number') return q.index + 1;
        if (typeof q.gameBlockIndex === 'number') return q.gameBlockIndex + 1;
        if (q.currentQuestion && typeof q.currentQuestion.index === 'number') return q.currentQuestion.index + 1;
        return null;
    }

    function collectAnswers(q) {
        const answers = [];
        const candidates = [];
        const payload = normalizeQuestionPayload(q);

        if (Array.isArray(payload.choices)) candidates.push(...payload.choices);
        if (Array.isArray(payload.answers)) candidates.push(...payload.answers);
        if (payload.answers && Array.isArray(payload.answers.answers)) candidates.push(...payload.answers.answers);
        if (payload.nextGameBlockData && Array.isArray(payload.nextGameBlockData.choices)) candidates.push(...payload.nextGameBlockData.choices);
        if (payload.question && Array.isArray(payload.question.choices)) candidates.push(...payload.question.choices);
        if (payload.firstGameBlockData && Array.isArray(payload.firstGameBlockData.choices)) candidates.push(...payload.firstGameBlockData.choices);

        candidates.forEach((choice, index) => {
            const text = getText(choice) || getText(choice.answer) || getText(choice.choice) || getText(choice.title) || getText(choice.label) || `Option ${index + 1}`;
            answers.push(text);
        });

        return answers;
    }

    function describeQuestion(q) {
        if (!q || typeof q !== 'object') {
            return [`QuestionReady: ${String(q)}`];
        }

        const lines = [];
        const questionData = normalizeQuestionPayload(q);
        const index = getQuestionIndex(q);
        const questionText = getText(questionData) || getText(questionData.question) || getText(questionData.prompt) || getText(questionData.title) || getText(questionData.description) || getText(questionData.content) || getText(questionData.quizQuestion) || getText(questionData.text);
        const questionType = questionData.type || q.type || q.questionType || 'unknown';
        const answers = collectAnswers(questionData);
        const imageUrls = getImageUrls(questionData);
        const choiceCount = typeof questionData.numberOfChoices === 'number' ? questionData.numberOfChoices : answers.length;

        lines.push(`Question ${index || '?'}: ${questionText || questionType}`);
        if (questionType) {
            lines.push(`Type: ${questionType}`);
        }
        if (choiceCount >= 0) {
            lines.push(`Choices: ${choiceCount}`);
        }
        if (answers.length) {
            lines.push('Answers:');
            answers.forEach((answer, idx) => lines.push(` - ${idx + 1}. ${answer}`));
        }
        if (imageUrls.length) {
            lines.push('Images:');
            imageUrls.forEach(url => lines.push(` - ${url}`));
        }
        if (!answers.length && !imageUrls.length && !questionText) {
            lines.push(`Payload: ${JSON.stringify(questionData)}`);
        }

        return lines;
    }

    const logJoined = info => event(`Joined: ${formatJoinInfo(info)}`);
    const logGameStart = data => {
        event('Game started');
        if (data && typeof data === 'object') {
            event(`Game info: ${formatJoinInfo(data)}`);
        }
    };
    const logQuestionReady = q => {
        event('Question ready');
        describeQuestion(q).forEach(line => console.log(style('[DETAIL]', colors.cyan), line));
    };
    const logQuestionStart = q => {
        event('Question started');
        describeQuestion(q).forEach(line => console.log(style('[DETAIL]', colors.cyan), line));
    };
    const logDisconnect = reason => {
        warn(`Disconnect: ${reason}`);
        process.exit(0);
    };

    client.on('Joined', logJoined);
    client.on('joined', logJoined);

    client.on('QuizStart', logGameStart);
    client.on('quizStart', logGameStart);
    client.on('GameStart', logGameStart);
    client.on('gameStart', logGameStart);

    client.on('QuestionReady', logQuestionReady);
    client.on('questionReady', logQuestionReady);
    client.on('QuestionStart', logQuestionStart);
    client.on('questionStart', logQuestionStart);

    client.on('Disconnect', logDisconnect);
    client.on('disconnect', logDisconnect);

    setInterval(() => {}, 1000);
} catch (e) {
    error('Please ensure kahoot.js-latest is installed (npm install kahoot.js-latest)');
    error(e.message || e);
    process.exit(1);
}
