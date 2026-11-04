import { useState } from 'react';

const DEFAULT_REPOSITORY = 'cs24-sopr/dhsn-minecraft-assets';
const PREVIOUS_WEEK_LOOKBACK_DAYS = 3;

type ReleaseCompareProps = {
    repository?: string;
};

type GitHubRelease = {
    tag_name: string;
    published_at: string | null;
    draft: boolean;
};

type Release = {
    tag: string;
    publishedAt: Date;
};

type State =
    | { status: 'idle' }
    | { status: 'loading' }
    | { status: 'ready'; url: string }
    | { status: 'empty' }
    | { status: 'error'; message: string };

function getWindowStart(now: Date): Date {
    const start = new Date(now);
    start.setHours(0, 0, 0, 0);

    const daysSinceMonday = (start.getDay() + 6) % 7;
    start.setDate(
        start.getDate() - daysSinceMonday - PREVIOUS_WEEK_LOOKBACK_DAYS,
    );

    return start;
}

function buildCompareUrl(
    repository: string,
    base: Release,
    target: Release,
): string {
    return `https://github.com/${repository}/compare/${encodeURIComponent(
        base.tag,
    )}...${encodeURIComponent(target.tag)}`;
}

export default function ReleaseCompare({
    repository = DEFAULT_REPOSITORY,
}: ReleaseCompareProps) {
    const [state, setState] = useState<State>({ status: 'idle' });

    async function generateUrl(): Promise<void> {
        setState({ status: 'loading' });

        try {
            const response = await fetch(
                `https://api.github.com/repos/${repository}/releases?per_page=100`,
                {
                    headers: {
                        Accept: 'application/vnd.github+json',
                    },
                },
            );

            if (!response.ok) {
                throw new Error(
                    `GitHub-API antwortete mit Status ${response.status}.`,
                );
            }

            const data = (await response.json()) as GitHubRelease[];
            const now = new Date();
            const windowStart = getWindowStart(now);

            const releases = data
                .map((release) => {
                    if (release.draft || !release.published_at) {
                        return null;
                    }

                    const publishedAt = new Date(release.published_at);
                    if (Number.isNaN(publishedAt.getTime())) {
                        return null;
                    }

                    return { tag: release.tag_name, publishedAt };
                })
                .filter((release): release is Release => release !== null)
                .sort(
                    (a, b) =>
                        a.publishedAt.getTime() - b.publishedAt.getTime(),
                );

            const inWindow = releases.filter(
                (release) =>
                    release.publishedAt >= windowStart &&
                    release.publishedAt <= now,
            );
            const beforeWindow = releases.filter(
                (release) => release.publishedAt < windowStart,
            );

            let base: Release | undefined;
            let target: Release | undefined;

            if (inWindow.length > 1) {
                base = inWindow[0];
                target = inWindow[inWindow.length - 1];
            } else if (inWindow.length === 1) {
                base = beforeWindow[beforeWindow.length - 1];
                target = inWindow[0];
            }

            if (!base || !target) {
                setState({ status: 'empty' });
                return;
            }

            setState({
                status: 'ready',
                url: buildCompareUrl(repository, base, target),
            });
        } catch (error) {
            setState({
                status: 'error',
                message:
                    error instanceof Error
                        ? error.message
                        : 'Die Releases konnten nicht geladen werden.',
            });
        }
    }

    return (
        <div>
            <button
                type="button"
                onClick={generateUrl}
                disabled={state.status === 'loading'}
            >
                {state.status === 'loading'
                    ? 'Lade Releases...'
                    : 'Vergleichs-URL erzeugen'}
            </button>

            {state.status === 'error' && <p>{state.message}</p>}

            {state.status === 'empty' && (
                <p>Für diese Kalenderwoche gibt es noch keinen Vergleich.</p>
            )}

            {state.status === 'ready' && (
                <p>
                    <a href={state.url}>{state.url}</a>
                </p>
            )}
        </div>
    );
}
