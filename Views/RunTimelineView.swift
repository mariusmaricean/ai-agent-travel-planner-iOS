import SwiftUI

struct RunTimelineView: View {
    @ObservedObject var viewModel: AgentViewModel

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            SectionHeader(
                title: "Agent Run",
                subtitle: viewModel.isRunning ? "Agent is acting" : "\(viewModel.steps.filter { $0.status == .done }.count) actions completed"
            )

            HStack(spacing: 10) {
                MetricCard(value: "\(viewModel.steps.count)", label: "steps", color: TravelPlannerColor.tealSoft)
                MetricCard(value: "3", label: "calls", color: TravelPlannerColor.limeSoft)
                MetricCard(value: "\(viewModel.savedCount)", label: "saved", color: TravelPlannerColor.goldSoft)
            }

            VStack(spacing: 10) {
                ForEach(viewModel.steps) { step in
                    RunStepRow(step: step)
                }
            }
        }
        .padding(14)
        .background(.white.opacity(0.72), in: RoundedRectangle(cornerRadius: 18, style: .continuous))
    }
}
