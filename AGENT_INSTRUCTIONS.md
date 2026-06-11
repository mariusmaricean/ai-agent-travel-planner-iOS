This file provides guidance to AI coding assistants when working with code in this repository.

Before editing Swift files, always read **SWIFT_STYLE_GUIDE.md** and follow those rules for formatting and Swift conventions.

## Project Context

- App name: TravelPlanner
- Platform: iOS
- UI framework: SwiftUI
- Primary app file: `TravelPlannerApp.swift`
- Xcode project: `TravelPlanner.xcodeproj`

## Working Rules

- Keep changes focused on the requested task.
- Avoid unrelated refactors or cosmetic churn.
- Preserve the existing SwiftUI architecture unless a change clearly improves maintainability.
- Verify Swift edits with `swiftc -parse TravelPlannerApp.swift` when possible.
