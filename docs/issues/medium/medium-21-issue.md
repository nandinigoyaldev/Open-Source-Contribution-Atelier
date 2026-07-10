# Enhance Lesson Text-to-Speech Quality and Customization Controls

- **Difficulty**: Medium
- **Category**: Frontend
- **Beginner Friendliness**: Yes, standard React hooks and UI controls.

---

### Description
The lesson text-to-speech engine's default voice can sound robotic, artificial, or hard to understand depending on the client platform. Users should be able to customize, test, and adjust the speech settings (voice, speed, and pitch) in real-time until it feels completely clear and natural.

### Expected Outcome
An interactive settings panel next to the "Listen" button in the lesson view that allows users to select their preferred system voice, adjust speed and pitch, and preview it.

### Acceptance Criteria
- [ ] Add a voice selector dropdown populated with available voices from `window.speechSynthesis.getVoices()`.
- [ ] Add custom sliders/controls for playback speed (rate: 0.5 to 2.0) and pitch (0.5 to 1.5).
- [ ] Implement a live settings preview so users can adjust settings until they are fully satisfied with the voice quality.
- [ ] Persist selected voice settings in `localStorage` so the settings apply automatically to subsequent lessons.

### Files Likely Affected
- [frontend/src/hooks/useTextToSpeech.ts](file:///Users/nandini/Downloads/open/Open-Source-Contribution-Atelier/frontend/src/hooks/useTextToSpeech.ts)
- [frontend/src/pages/LessonPage.tsx](file:///Users/nandini/Downloads/open/Open-Source-Contribution-Atelier/frontend/src/pages/LessonPage.tsx)
