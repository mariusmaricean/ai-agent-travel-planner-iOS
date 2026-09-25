import SwiftUI

struct RunStepRow: View {
    var step: RunStep

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: statusSymbol)
                .foregroundStyle(iconColor)
                .frame(width: 36, height: 36)
                .background(iconBackground, in: Circle())

            VStack(alignment: .leading, spacing: 3) {
                Text(step.title)
                    .font(.subheadline.weight(.semibold))
                Text(step.detail)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }

            Spacer()

            VStack(alignment: .trailing, spacing: 4) {
                Text(statusText)
                    .font(.caption2.bold())
                    .foregroundStyle(statusTextColor)
                Text(step.tag)
                    .font(.caption2.bold())
                    .foregroundStyle(.secondary)
            }
            .padding(.horizontal, 8)
            .padding(.vertical, 5)
            .background(TravelPlannerColor.paper, in: Capsule())
        }
        .padding(12)
        .background(.white, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
    }

    private var statusSymbol: String {
        switch step.status {
        case .queued: step.symbol
        case .active: "ellipsis"
        case .done: "checkmark"
        case .failed: "xmark"
        }
    }

    private var statusText: String {
        switch step.status {
        case .queued: "Queued"
        case .active: "Running"
        case .done: "Done"
        case .failed: "Failed"
        }
    }

    private var statusTextColor: Color {
        switch step.status {
        case .queued: .secondary
        case .active: TravelPlannerColor.teal
        case .done: TravelPlannerColor.lime
        case .failed: TravelPlannerColor.coral
        }
    }

    private var iconColor: Color {
        switch step.status {
        case .queued: .secondary
        case .active: .white
        case .done: .white
        case .failed: .white
        }
    }

    private var iconBackground: Color {
        switch step.status {
        case .queued: TravelPlannerColor.paper
        case .active: TravelPlannerColor.teal
        case .done: TravelPlannerColor.lime
        case .failed: TravelPlannerColor.coral
        }
    }
}
