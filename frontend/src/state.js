/**
 * Frontend-only ephemeral view state.
 * Not game truth — just UI state like "is input disabled" and "current turn data."
 */
export const state = {
  sessionId: null,
  isSubmitting: false,
  currentTurn: null,
  addressedCharacter: null,
  inputText: '',
  errorMessage: null,
};
