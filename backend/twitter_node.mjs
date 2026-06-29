import { Scraper } from '@the-convocation/twitter-scraper';
import fs from 'fs';
import path from 'path';

async function main() {
    const query = process.argv[2];
    if (!query) {
        console.error("No query provided");
        process.exit(1);
    }

    let authToken = '';
    let ct0 = '';
    
    try {
        const envPath = path.join(process.cwd(), '.env');
        const env = fs.readFileSync(envPath, 'utf-8');
        const lines = env.split('\n');
        for (const line of lines) {
            if (line.startsWith('TWITTER_AUTH_TOKEN=')) {
                authToken = line.split('=')[1].trim().replace(/['"]/g, '');
            }
            if (line.startsWith('TWITTER_CT0=')) {
                ct0 = line.split('=')[1].trim().replace(/['"]/g, '');
            }
        }
    } catch(e) {}

    if (!authToken || !ct0) {
        console.log(JSON.stringify({ error: "Missing authentication in .env" }));
        process.exit(0);
    }

    const scraper = new Scraper();
    const cookieStrings = [
        `ct0=${ct0}`,
        `auth_token=${authToken}`
    ];
    await scraper.setCookies(cookieStrings);
    
    try {
        const isLoggedIn = await scraper.isLoggedIn();
        if (!isLoggedIn) {
            console.log(JSON.stringify({ error: "Login failed with provided cookies" }));
            process.exit(0);
        }

        // SearchMode 2 = Latest tweets
        const tweets = scraper.searchTweets(query, 60, 2);
        const results = [];
        let count = 0;
        
        for await (const t of tweets) {
            results.push({
                text: t.text,
                user: {
                    name: t.name || t.username,
                    screen_name: t.username
                },
                created_at: t.timeParsed ? new Date(t.timeParsed).toISOString() : new Date().toISOString()
            });
            count++;
            if (count >= 60) break;
        }

        console.log(JSON.stringify({ tweets: results }));
    } catch(e) {
        console.log(JSON.stringify({ error: e.toString() }));
    }
}

main().catch(e => {
    console.log(JSON.stringify({ error: e.toString() }));
});
