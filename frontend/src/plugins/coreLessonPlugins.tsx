import React from 'react';
import { lessonPluginRegistry } from './LessonPluginRegistry';
import { PythonSandbox } from '../components/ui/PythonSandbox';
import { CollabPythonSandbox } from '../components/ui/CollabPythonSandbox';
import { JSSandbox } from '../components/ui/JSSandbox';
import { InteractiveDebugger } from '../components/ui/InteractiveDebugger';

// 1. Python Sandbox Plugin
lessonPluginRegistry.register({
  type: 'python_sandbox',
  version: '1.0',
  canHandle: (lesson) => !!lesson.pythonExercise,
  component: ({ lesson, onSuccess }) => {
    const isCollab = new URLSearchParams(window.location.search).get("session");
    if (isCollab) {
      return (
        <CollabPythonSandbox
          exercise={lesson.pythonExercise!}
          roomId={isCollab}
          onSuccess={() => onSuccess(lesson.points || 20)}
        />
      );
    }
    return (
      <PythonSandbox
        exercise={lesson.pythonExercise!}
        onSuccess={() => onSuccess(lesson.points || 20)}
      />
    );
  }
});

// 2. JavaScript Sandbox Plugin
lessonPluginRegistry.register({
  type: 'js_sandbox',
  version: '1.0',
  canHandle: (lesson) => !!lesson.jsExercise,
  component: ({ lesson, onSuccess }) => (
    <JSSandbox
      exercise={lesson.jsExercise!}
      onSuccess={() => onSuccess(lesson.points || 20)}
    />
  )
});

// 3. Interactive Debugger Plugin
lessonPluginRegistry.register({
  type: 'interactive_debugger',
  version: '1.0',
  canHandle: (lesson) => !!lesson.debugExercise,
  component: ({ lesson, onSuccess }) => (
    <InteractiveDebugger
      exercise={lesson.debugExercise!}
      onSuccess={() => onSuccess(lesson.points || 30)}
    />
  )
});
