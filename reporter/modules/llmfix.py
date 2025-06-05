import os

from openai import OpenAI
import dotenv

dotenv.load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# client = OpenAI(api_key=OPENAI_API_KEY)


def patch_code(vulnerable_code, full_filename):
    formatted_vuln_code = []
    for i, line in enumerate(vulnerable_code.splitlines()	):
    #for i, line in enumerate(vulnerable_code):
        formatted_vuln_code.append(f'{str(i + 1).zfill(4)}#{line}')
    formatted_vuln_code = '\n'.join(formatted_vuln_code) + '\n'
    # Your OpenAI API key

    # Combining the code with the instructions to form the prompt
    prompt = f"""You only provide the final secure patch file.
Do not make non-security changes.
In the error message you are creating, do not show file name, so it won't cause other issues.
Keep the changes minimal but clean and prefer early deny returns in code.
Do not change whitespaces and previous codes, only add the piece of code you have to.
Return patch file for only changes, and obey all the instructions I mention, as the instructions are all mandatory.
Fix the path traversal vulnerability in an efficient, clean and secure way.
Follow best practices of how best companies in the world are doing it.
Keep it clean and minimal and return a patch file that respects 100% accurate the line number changes.
Choose best lines to fix the code based on reading and understanding the code first.
To fix this vulnerability, you check for the request input to the server, and add a IF condition to compare of the request path is equal to the normalized version of the path or not (with 3 equals ===).
For example if (( uri OR pathname OR other related variable).includes('..')), BLOCK that request, and respond the request with request is blocked.
You can't trust the output of path.join function as the return value will be normalized and won't contain the payload('..'). Also make sure to exactly show same code when you are printing the patch for non-changed lines. If you print something different, the patch will not work.
Only add a single if condition and do not touch other parts of the code. Do not add else, instead return in the blocking if condition.
Produce a very clean patch, without code duplicates.
The code I provide you is 100% vulnerable, so instead of relying on any available mitigations, you must apply the mitigation exactly I asked in the promopt(always check for existance of two dots, similar to what happens in).
Make sure your patch file contains ONLY security changes.
Make sure your patch file does not apply non-security changing issues.
Do not add empty lines in patch. Follow same coding practice, indentation and coding styles that in the source code.
Make sure to not remove any codes, just add your patch. Also, do not add non-security related codes.
If the source code, modifies the URI in any step(for example decodeURI(uri), decodeURIComponent(uri) or unescape(uri) or similar things), make sure to treat the URI exactly the same way the server treats the URI. So if it used method X you have to use method X on it as well(X can be URI decoding or similar things). 
Your patch file MUST CONTAIN THE MITIGATION I EXPLAINED or a mitigation you think is similar and best.
If the the request didn't match, send a 403 response, without saying 'Hacking attempt'.
Don't add any regex or blacklist approaches, just do what I told you.
Follow software engineering best practices, specially KISS and DRY and clean code.
Don't mix different mix IF conditions together.
Prefer early deny if request does not look secure.
Use separate IF condition for security check and don't mix other logics in same IF condition.
Prefer add a new independent logic to secure the app instead of changing previous logic.
Don't corrupt the valid logic of program when adding new IF conditions.
Do not add or modify other parts of the code, only add the required patch.
Only reject path queries that seem insecure.
It must contain file name and line numbers.
Make sure the patch is not malformed.
Add the secured version where it's required, not in other places, possibly best place is the start of a function that handles that path, only if there are no routing happening in the source code.
The vulnerable code is shown as START``` then a new line, and the end is shown with a new line followed by ```END
To make sure that you'll handle lines correctly, I'll add each line number as decimal with length of 4 at start of the prompt with a sharp sign. Here is an example input:
For example:

START```
0001#const a = () => 5;
0002#let b=1;
0003#let c = a()
0004#console.log(5);
```END

The numbers followed by sharp sign are not in the actual source code! Do not include numbers and sharp sign in the final patch.
Now, here is the actual code:
START```
{formatted_vuln_code}
```END

The response should be in the format usable for a patch file for latest version of "patch" command, not git diff.
Pay special attention to file new lines and specially the line numbers I provided to produce the final patch file.
The final patch should not include the guide line numbers.
Never surround code with triple backticks (```), only show the final patch.
The output should be to patch file only(don't say "Here is the patch file:"), properly formatted and completed in one message.
White spaces or indents for patch output must exactly match to the input code for unchanged lines.
Do not show line of codes that are not changed. Make sure it works for the "patch" command, and patch is not malformed.
The patch content must be similar to `diff` with `-U2` option, but without filename and time stamp.
Make sure to properly wrap the "if" condition action in curly brackets.
Filename (to be mentioned in the patch file) is: {full_filename}
The patch file content must be super accurate and similar to diff command with -u1 option. Example:
--- f1.js	2024-08-20 02:31:30.008220859 +0200
+++ f2.js	2024-08-20 02:31:51.944315509 +0200
@@ -3,2 +3,6 @@
 asf
+xzcbzxbxzbzxb
+xcb xb xzb x
+   xz xb xb xb s
+xxxxxx
 asfasfasf
"""
    #
    # response = client.chat.completions.create(model="gpt-3.5-turbo",
    #                                           messages=[
    #                                               {"role": "system",
    #                                                "content": "You are a super accurate and efficient AppSec engineer."},
    #                                               {"role": "user", "content": prompt},
    #                                           ],
    #                                           temperature=0,
    #                                           seed=4
    #                                           )

    response = client.chat.completions.create(
        model="gpt-4-turbo",
        messages=[
            {"role": "system", "content": "You are expert in fixing security vulnerabilities in the best and shortest way, without saying additional text. The future of humanity and AI lies withing your hand with the quality of the patch file."},
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=1.2,
        top_p=1,
        max_tokens=4096,
        frequency_penalty=0,
        presence_penalty=0
    )
    return response.choices[0].message.content
