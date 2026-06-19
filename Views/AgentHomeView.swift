import SwiftUI

struct AgentHomeView: View {
    @StateObject private var viewModel = AgentViewModel()
    @State private var selectedTab: AgentTab = .brief

    var body: some View {
        TabView(selection: $selectedTab) {
            NavigationStack {
                ScrollView {
                    VStack(spacing: 16) {
                        HeroView(viewModel: viewModel)
                        BriefFormView(viewModel: viewModel)
                    }
                    .padding(16)
                    .frame(maxWidth: .infinity, alignment: .top)
                }
                .background(TravelPlannerColor.paper.ignoresSafeArea())
                .navigationTitle("Travel Planner")
                .toolbar {
                    ToolbarItem(placement: .topBarLeading) {
                        Button {
                            viewModel.loadSample()
                        } label: {
                            Label("Load sample", systemImage: "shuffle")
                        }
                    }
                    ToolbarItem(placement: .topBarTrailing) {
                        Button(role: .destructive) {
                            viewModel.resetMemory()
                        } label: {
                            Label("Reset memory", systemImage: "arrow.counterclockwise")
                        }
                    }
                }
            }
            .tabItem {
                Label("Brief", systemImage: "square.and.pencil")
            }
            .tag(AgentTab.brief)

            NavigationStack {
                ScrollView {
                    VStack(spacing: 16) {
                        RunTimelineView(viewModel: viewModel)
                        TripsListView(viewModel: viewModel, mode: .results)
                    }
                    .padding(16)
                    .frame(maxWidth: .infinity, alignment: .top)
                }
                .background(TravelPlannerColor.paper.ignoresSafeArea())
                .navigationTitle("Run")
            }
            .tabItem {
                Label("Run", systemImage: "waveform.path.ecg")
            }
            .tag(AgentTab.run)

            NavigationStack {
                ScrollView {
                    VStack(spacing: 16) {
                        TripsListView(viewModel: viewModel, mode: .saved)
                        MemoryView(viewModel: viewModel)
                    }
                    .padding(16)
                    .frame(maxWidth: .infinity, alignment: .top)
                }
                .background(TravelPlannerColor.paper.ignoresSafeArea())
                .navigationTitle("Saved")
            }
            .tabItem {
                Label("Saved", systemImage: "tray.full")
            }
            .tag(AgentTab.saved)
        }
        .tint(TravelPlannerColor.teal)
    }
}

enum AgentTab {
    case brief
    case run
    case saved
}
