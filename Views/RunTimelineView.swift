import SwiftUI

struct RunTimelineView: View {
    @ObservedObject var viewModel: AgentViewModel

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            SectionHeader(
                title: "Agent Run",
                subtitle: viewModel.timelineSubtitle
            )

            HStack(spacing: 10) {
                MetricCard(value: "\(viewModel.steps.count)", label: "steps", color: TravelPlannerColor.tealSoft)
                MetricCard(value: "\(viewModel.agentStageCount)", label: "agents", color: TravelPlannerColor.limeSoft)
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
