<?php

namespace App\Http\Controllers;

use Illuminate\Foundation\Auth\Access\AuthorizesRequests;
use Illuminate\Foundation\Validation\ValidatesRequests;
use Illuminate\Routing\Controller as BaseController;

/**
 * @OA\Info(
 *     version="1.0",
 *     title="Example for response examples value"
 * )
 */

/**
 * @OA\Info(
 *      version="1.0.0",
 *      title="Laravel OpenApi Documentation",
 *      description="L5 Swagger OpenApi description",
 *      @OA\Contact(
 *          email="info@iranicard.ir"
 *      ),
 *      @OA\License(
 *          name="Apache 2.0",
 *          url="http://www.apache.org/licenses/LICENSE-2.0.html"
 *      )
 * )
 *
 * @OA\Server(
 *      url=L5_SWAGGER_CONST_HOST,
 *      description="Demo API Server Of Ticket Sales."
 * )

 *
 * @OA\Tag(
 *     name="Projects",
 *     description="API Endpoints of Ticket Sales"
 * )
 */
class Controller extends BaseController
{
    use AuthorizesRequests, ValidatesRequests;
}
