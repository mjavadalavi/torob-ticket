<?php

namespace App\Http\Controllers\API;

use App\Enums\Status;
use App\Enums\StatusCode;
use App\Http\Controllers\Controller;
use App\Http\Requests\StoreWeeklyScheduleRequest;
use App\Models\WeeklySchedule;
use Illuminate\Http\JsonResponse;
use Symfony\Component\HttpFoundation\Response;

class WeeklyScheduleController extends Controller
{
    /**
     * @OA\Post(
     *     path="/weekly-schedule",
     *     summary="Add a new weekly schedule",
     *     operationId="addweeklyschedule",
     *     tags={"weekly-schedule"},
     *     @OA\RequestBody(
     *         @OA\MediaType(
     *             mediaType="application/json",
     *             @OA\Schema(
     *                 @OA\Property(
     *                     property="source_city_id",
     *                     type="string"
     *                 ),
     *                 @OA\Property(
     *                     property="source_terminal_id",
     *                     type="string"
     *                 ),
     *                 @OA\Property(
     *                     property="destination_city_id",
     *                     type="string"
     *                 ),
     *                 @OA\Property(
     *                     property="destination_terminal_id",
     *                     type="string"
     *                 ),
     *                 @OA\Property(
     *                     property="moving_day_number",
     *                     type="integer"
     *                 ),
     *                 @OA\Property(
     *                     property="moving_time_seconds",
     *                     type="integer"
     *                 ),
     *                 @OA\Property(
     *                     property="traveling_time",
     *                     type="string"
     *                 ),
     *                 @OA\Property(
     *                     property="capacity",
     *                     type="string"
     *                 ),
     *                 @OA\Property(
     *                     property="bus_type",
     *                     type="integer"
     *                 ),
     *                 @OA\Property(
     *                     property="price",
     *                     type="integer"
     *                 ),
     *                 example={
     *                          "source_city_id":"esf",
     *                          "source_terminal_id":"5",
     *                          "destination_city_id":"teh",
     *                          "destination_terminal_id":"3",
     *                          "moving_day_number":0,
     *                          "moving_time_seconds":28800,
     *                          "traveling_time":240,
     *                          "capacity":26,
     *                          "bus_type":1,
     *                          "price":2000000
     *                     }
     *             )
     *         )
     *     ),
     *     @OA\Response(
     *         response="201",
     *         description="ok",
     *         content={
     *             @OA\MediaType(
     *                 mediaType="application/json",
     *                 @OA\Schema(
     *                     example={
     *                          "id":"1",
     *                          "source_city_id":"esf",
     *                          "source_terminal_id":"5",
     *                          "destination_city_id":"teh",
     *                          "destination_terminal_id":"3",
     *                          "moving_day_number":0,
     *                          "moving_time_seconds":28800,
     *                          "traveling_time":240,
     *                          "capacity":26,
     *                          "bus_type":1,
     *                          "price":2000000
     *                     }
     *                 )
     *             )
     *         }
     *     ),
     *   @OA\Response(
     *          response=400,
     *          description="Bad Request",
     *          content={
     *             @OA\MediaType(
     *                 mediaType="application/json",
     *                 @OA\Schema(
     *                     example={
     *                          "status":"HTTP Bad Request",
     *                          "code":"400",
     *                          "data":"your request don't have some parameter."
     *                     }
     *                 )
     *             )
     *         }
     *      )
     * )
     */
    public function store(StoreWeeklyScheduleRequest $request): JsonResponse
    {
        if ($request->validated()) {
            $weekly_schedule = WeeklySchedule::create($request->all());
            return response() -> json($weekly_schedule)
                ->setStatusCode(Response::HTTP_CREATED)
                ->header('Content-Type', 'application/json');
        }else{
            return response()->json(['status' => Status::HTTP_BAD_REQUEST , "code" => StatusCode::Failed, "data"=> "your request don't have some parameter."])
                ->setStatusCode(Response::HTTP_BAD_REQUEST)
                ->header('Content-Type', 'application/json');
        }
    }
}


