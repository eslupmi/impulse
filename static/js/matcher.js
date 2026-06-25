const matcherPattern = /^(\w+)\s?(=|!=|=~|!~)\s?"(.+)"$/;

function isValidRegex(pattern) {
    try {
        new RegExp(pattern);
        return true;
    } catch (e) {
        return false;
    }
}

function validateMatcher(matcher) {
    const query = String(matcher ?? "").trim();
    if (!query) {
        return {ok: false, reason: "Matcher cannot be empty"};
    }
    const match = query.match(matcherPattern);
    if (!match) {
        return {
            ok: false,
            reason: 'Use label op "value" with op =, !=, =~, or !~',
        };
    }
    const [, label, operator, value] = match;
    if (!value) {
        return {ok: false, reason: "Matcher value cannot be empty"};
    }
    if ((operator === "=~" || operator === "!~") && !isValidRegex(value)) {
        return {ok: false, reason: "Invalid regex in matcher"};
    }
    return {ok: true, formatted: `${label}${operator}"${value}"`};
}

function validateAndFormatMatcher(query) {
    const result = validateMatcher(query);
    return result.ok ? result.formatted : null;
}

export {
    validateMatcher,
    validateAndFormatMatcher,
};
