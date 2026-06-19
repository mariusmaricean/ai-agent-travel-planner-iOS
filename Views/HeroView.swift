import SwiftUI

struct HeroView: View {
    @ObservedObject var viewModel: AgentViewModel

    var body: some View {
        ZStack(alignment: .bottomLeading) {
            Image("TravelPlannerHero")
                .resizable()
                .scaledToFill()
                .frame(height: 258)
                .clipped()

            LinearGradient(
                colors: [.black.opacity(0.68), .black.opacity(0.16), .black.opacity(0.82)],
                startPoint: .top,
                endPoint: .bottom
            )

            VStack(alignment: .leading, spacing: 18) {
                HStack(spacing: 8) {
                    Image(systemName: "sparkles")
                    Text("Autonomous travel run")
                        .font(.caption.weight(.semibold))
                }
                .padding(.horizontal, 10)
                .padding(.vertical, 7)
                .background(.white.opacity(0.16), in: Capsule())

                Spacer()

                HStack(alignment: .bottom) {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Plan the next move.")
                            .font(.system(size: 40, weight: .black, design: .rounded))
                            .foregroundStyle(.white)
                            .lineLimit(2)
                            .minimumScaleFactor(0.75)

                        Text("Flights, days, constraints, and saved state in one agent pass.")
                            .font(.subheadline)
                            .foregroundStyle(.white.opacity(0.82))
                            .fixedSize(horizontal: false, vertical: true)
                    }

                    Spacer(minLength: 10)

                    StatusChip(text: viewModel.runStatus)
                }
            }
            .padding(16)
        }
        .frame(height: 258)
        .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
        .shadow(color: .black.opacity(0.14), radius: 18, y: 12)
        .accessibilityElement(children: .combine)
    }
}
