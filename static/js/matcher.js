const matcherPattern = /^([a-zA-Z_][a-zA-Z0-9_]*)\s?(=|!=|=~|!~)\s?(["'`])(.*)\3$/;

function isValidRegex(pattern) {
    try {
        new RegExp(pattern);
        return true;
    } catch {
        return false;
    }
}

function parseMatcher(matcher) {
    const match = matcherPattern.exec(matcher);
    return match && {label: match[1], operator: match[2], value: match[4]};
}

function validateMatcher(matcher) {
    const query = String(matcher ?? "").trim();
    if (!query) {
        return {ok: false, reason: "Matcher cannot be empty"};
    }
    const parsed = parseMatcher(query);
    if (!parsed) {
        return {
            ok: false,
            reason: 'Use label op "value" with op =, !=, =~, or !~ and quotes ", \' or `',
        };
    }
    const {operator, value} = parsed;
    if (!value) {
        return {ok: false, reason: "Matcher value cannot be empty"};
    }
    if ((operator === "=~" || operator === "!~") && !isValidRegex(value)) {
        return {ok: false, reason: "Invalid regex in matcher"};
    }
    return {ok: true};
}

function validateAndFormatMatcher(query) {
    const q = String(query ?? "").trim();
    return validateMatcher(q).ok ? q : null;
}

export {
    isValidRegex,
    parseMatcher,
    validateMatcher,
    validateAndFormatMatcher,
};
