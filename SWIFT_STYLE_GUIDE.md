# Swift Style Guide

Follow these rules when editing Swift or SwiftUI code in this repository.

## General Swift standards

- Prefer clear, small SwiftUI views over large nested view bodies.
- Keep models, view state, and helper types strongly typed.
- Use `@MainActor` for observable app state that drives SwiftUI.
- Prefer `let` over `var` unless mutation is required.
- Keep async work explicit with `Task` and `async` functions.
- Avoid force unwraps unless the value is guaranteed by construction.
- Prefer clarity over cleverness.
- Follow Swift API Design Guidelines.
- Write code that feels native to Apple platforms.
- Use descriptive names with correct grammar.
- Prefer value types (`struct`, `enum`) over classes unless reference semantics are required.
- Mark classes `final` unless subclassing is required.
- Keep functions small and focused.
- Avoid deeply nested logic; use early returns.
- Prefer composition over inheritance.
- Do not add comments that restate obvious code.
- Do add `// MARK:` sections for larger types when helpful.

## SwiftUI

- Use native controls first: `Button`, `Picker`, `Toggle`, `Slider`, `DatePicker`, `TextField`, and `TextEditor`.
- Keep view modifiers readable by grouping related layout, styling, and accessibility modifiers together.
- Preserve Dynamic Type behavior; avoid fixed layouts that clip text on smaller iPhones.
- Use SF Symbols for icons.
- Keep reusable styling in local helper views or color/type helpers when it reduces repetition.
- Views must remain composable.
- If a SwiftUI `body` exceeds ~80 lines, extract subviews.

## Formatting

- Use four spaces for indentation.
- Keep one primary type per conceptual section.
- Prefer concise computed properties for derived view state.
- Avoid unrelated refactors while making feature changes.

## Verification

- Run `swiftc -parse TravelPlannerApp.swift` after Swift edits when possible.
- For project-level changes, run an Xcode build for the `TravelPlanner` scheme when possible.
