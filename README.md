# Travel Planner for iOS

This is a SwiftUI-native version of the mobile-first autonomous travel agent prototype.

## Files

- `TravelPlanner.xcodeproj`: Xcode project with a single SwiftUI iOS app target.
- `TravelPlannerApp.swift`: complete SwiftUI app shell with trip brief, agent run timeline, saved trips, and UserDefaults-backed memory.
- `Assets.xcassets/TravelPlannerHero.imageset`: generated travel visual used by the iOS hero.

## Run

Open `TravelPlanner.xcodeproj` in Xcode, select the `TravelPlanner` scheme, and run it on an iPhone simulator or device.

## Agent Integration Points

- Replace `makeTrips()` with live tool results from your backend.
- Route `searchFlights(origin, destination, dates, budget)` to a flight provider function.
- Route `buildItinerary(fares, constraints, memory)` to your planning/model function.
- Keep `updateMemory(bestTrip:)` as the local state write, or sync the notes to your app account layer.

The included implementation intentionally simulates tool calls on-device so the UI can run before any API keys, auth, or backend wiring exists.
